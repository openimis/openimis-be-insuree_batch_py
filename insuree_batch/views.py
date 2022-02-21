import glob
import io
import os
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
from turtle import width

from django.http import FileResponse
from django.shortcuts import get_object_or_404, render

from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _
from numpy import append
import qrcode
import qrcode.image.svg

from . import services
from .apps import InsureeBatchConfig
from .models import InsureeBatch

import os
from PyPDF2 import PdfFileMerger, PdfFileReader
import svg_stack as ss


def batch_qr(request):
    # if not request.user.has_perms(InsureeBatchConfig.gql_query_batch_runs_perms):
    #     raise PermissionDenied(_("unauthorized"))
    batch_id = request.GET.get("batch")
    batch = get_object_or_404(InsureeBatch, id=batch_id)

    factory = qrcode.image.svg.SvgImage
    insuree_ids = []

    file_name = "front.svg"
    template_folder = "templates/insuree_batch"
    abs_path = Path(__file__).absolute().parent
    file_fullpath = F'{abs_path}/{template_folder}/{file_name}'
    card_folder = F'{abs_path}/cards/{batch.id}'

    # if the pdf is already created display it
    if os.path.isfile(F'{abs_path}/cards/{batch.id}.pdf'):
        return FileResponse(open(F'{abs_path}/cards/{batch.id}.pdf', 'rb'), content_type='application/pdf')

    if os.path.exists(card_folder) == False:
        os.makedirs(card_folder)

    for item in batch.insuree_numbers.all():
        img = qrcode.make(
            item.insuree_number, image_factory=factory, box_size=10, border=0
        )

        stream = BytesIO()
        img.save(stream)
        # insuree_ids.append(
        #     {"insuree_number": item.insuree_number,
        #         "qr": stream.getvalue().decode()}
        # )

        with open(file_fullpath, "r") as f:
            card = f.read()

        location = "National"
        if batch.location != None:
            location = batch.location.name

        card = card.replace("@@SerialNumber", "")
        card = card.replace("@@InsuranceNumber", item.insuree_number)
        card = card.replace("@@Location", location)
        card = card.replace(
            "@@QRCode", stream.getvalue().decode().replace("<?xml version='1.0' encoding='UTF-8'?>", "")
            .replace("width=\"21mm\" height=\"21mm\"", "width=\"100%\" viewBox=\"0 0 100 100\""))

        with open(F'{card_folder}/{item.insuree_number}.svg', "wt") as f:
            f.write(card)

        insuree_ids.append(
            {"insuree_number": item.insuree_number,
                "qr": card}
        )

    doc = ss.Document()
    all_svgs = [f for f in glob.glob(F'{card_folder}/*.svg')]

    layout1 = ss.VBoxLayout()
    layout1.setSpacing(10)
    counter = 0
    images_on_page = int(os.environ.get("IMAGES_ON_PAGE") or 1)
    image_counter = 1
    merged_list = []

    if (images_on_page > 1):
        for file in all_svgs:

            layout1.addSVG(file, alignment=ss.AlignCenter)
            counter = counter + 1

            if (counter == images_on_page or all_svgs.index(file) == len(all_svgs) - 1):
                counter = 0
                doc.setLayout(layout1)
                filename = F'{abs_path}/cards/{batch.id}/{image_counter}.svg'
                merged_list.append(filename)
                doc.save(filename)
                image_counter = image_counter + 1

                layout1 = ss.VBoxLayout()
                layout1.setSpacing(10)
    else:
        merged_list = all_svgs

    inkscale_path = os.environ.get("INKSCALE")

    for merged_image in merged_list:
        pdf_abspath = merged_image.split('.')[0]
        p = subprocess.run([
            inkscale_path + 'inkscape', '--without-gui',  '--export-area-drawing', merged_image,  '--export-pdf', F'{pdf_abspath}' + '.pdf'])

    merged_object = PdfFileMerger()

    all_pdfs = [f for f in glob.glob(F'{card_folder}/*.pdf')]

    for pdf in all_pdfs:
        merged_object.append(PdfFileReader(pdf, 'rb'))

    merged_object.write(F'{abs_path}/cards/{batch.id}.pdf')

    # Remove files
    shutil.rmtree(card_folder)

    return FileResponse(open(F'{abs_path}/cards/{batch.id}.pdf', 'rb'), content_type='application/pdf')

    # return render(
    #     request,
    #     "insuree_batch/batch_qr.html",
    #     {"insuree_ids": insuree_ids, "batch": batch},
    # )


def export_insurees(request):
    if not request.user.has_perms(InsureeBatchConfig.gql_query_batch_runs_perms):
        raise PermissionDenied(_("unauthorized"))

    dry_run = request.GET.get("dryRun", "false").lower() == "true"
    batch_id = request.GET.get("batch")
    count = request.GET.get("count")

    if batch_id:
        batch = get_object_or_404(InsureeBatch, id=batch_id)
    else:
        batch = None

    zip_file = services.export_insurees(batch, count, dry_run)
    response = FileResponse(open(zip_file.name, "rb"),
                            content_type="application/zip")
    response["Content-Disposition"] = "attachment; filename=%s" % os.path.basename(
        zip_file.name
    )
    response["Content-Length"] = os.path.getsize(zip_file.name)
    return response
