import glob
import io
import os
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
from turtle import width

from django.http import FileResponse, HttpResponse
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
from django.conf import settings


def batch_qr(request):
    # if not request.user.has_perms(InsureeBatchConfig.gql_query_batch_runs_perms):
    #     raise PermissionDenied(_("unauthorized"))

    batch_id = request.GET.get("batch")
    batch = get_object_or_404(InsureeBatch, id=batch_id)

    factory = qrcode.image.svg.SvgImage

    file_name_front = InsureeBatchConfig.insuree_card_template_front_name
    file_name_back = InsureeBatchConfig.insuree_card_template_back_name
    template_folder = InsureeBatchConfig.template_folder
    output_format = InsureeBatchConfig.output_format
    abs_path = Path(settings.BASE_DIR).parent
    file_fullpath_front = F'{abs_path}/{template_folder}/{file_name_front}'
    file_fullpath_back = F'{abs_path}/{template_folder}/{file_name_back}'
    module_abs_path = Path(__file__).absolute().parent
    card_folder = F'{module_abs_path}/cards/{batch.id}'

    if file_name_front == '' and file_name_back == '':
        return HttpResponse("Template not defined")

    if file_name_front != '' and os.path.exists(file_fullpath_front) == False:
        return HttpResponse("Front template not found")

    if file_name_back != '' and os.path.exists(file_fullpath_back) == False:
        return HttpResponse("Back template not found")

    # if the pdf is already created and the output option is set to PDF display it

    if output_format.lower() == 'pdf' and os.path.isfile(F'{module_abs_path}/cards/{batch.id}.pdf'):
        return FileResponse(open(F'{module_abs_path}/cards/{batch.id}.pdf', 'rb'), content_type='application/pdf')

    # if the svg is already created and the output option is set to SVG display it
    if output_format.lower() == 'svg' and os.path.isfile(F'{module_abs_path}/cards/{batch.id}.zip'):
        return FileResponse(open(F'{module_abs_path}/cards/{batch.id}.zip', 'rb'), content_type='application/zip')

    if os.path.exists(F'{card_folder}/front') == False:
        os.makedirs(F'{card_folder}/front')

    if os.path.exists(F'{card_folder}/back') == False:
        os.makedirs(F'{card_folder}/back')

    # Replace parameters value with actual values
    for item in batch.insuree_numbers.all():
        img = qrcode.make(
            item.insuree_number, image_factory=factory, box_size=10, border=0
        )

        stream = BytesIO()
        img.save(stream)

        # Writing the front of the ID
        if file_name_front != '':
            prepare_svg(file_fullpath_front,
                        F'{card_folder}/front', batch, item, stream)

        # Writing the back of the ID
        if file_name_back != '':
            prepare_svg(file_fullpath_back,
                        F'{card_folder}/back', batch, item, stream)

    if output_format.lower() == 'pdf':
        handle_pdf(file_name_front, file_name_back,
                   card_folder, module_abs_path, batch.id)
        return FileResponse(open(F'{module_abs_path}/cards/{batch.id}.pdf', 'rb'), content_type='application/pdf')
    else:
        shutil.make_archive(F'{module_abs_path}/cards/{batch.id}',
                            'zip', F'{module_abs_path}/cards/{batch.id}')

        # Remove files/folder
        shutil.rmtree(card_folder)

        return FileResponse(open(F'{module_abs_path}/cards/{batch.id}.zip', 'rb'), content_type='application/zip')


def handle_pdf(front_name, back_name, card_folder, working_dir, batch_id):
    # Merge all the front svg files based on default configuration 'images_on_page'
    if front_name != '':
        merged_list_front = merge_svgs(
            F'{card_folder}/front', working_dir, batch_id)

        # Write PDFs (Front)
        write_pdf(merged_list_front)

    # Merge all the back svg files based on default configuration 'images_on_page'
    if back_name != '':
        merged_list_back = merge_svgs(
            F'{card_folder}/back', working_dir, batch_id)

        # Write PDFs (Back)
        write_pdf(merged_list_back)

    # Merge all the PDFs in a single PDF file
    if front_name != '':
        merge_pdfs(F'{card_folder}/front',
                   F'{working_dir}/cards/{batch_id}', '1')

    if back_name != '':
        merge_pdfs(F'{card_folder}/back',
                   F'{working_dir}/cards/{batch_id}', '2')

    merge_pdfs(card_folder, F'{working_dir}/cards', batch_id)

    # Remove files/folder
    shutil.rmtree(card_folder)


def prepare_svg(source_path, destination_path, batch, item, stream):
    with open(source_path, "r") as f:
        card_front = f.read()

    card_front = write_parameter_values(card_front, batch, item, stream)

    with open(F'{destination_path}/{item.insuree_number}.svg', "wt") as f:
        f.write(card_front)


def write_parameter_values(card, batch, insuree_number, qr_code_stream):
    location = "National"
    if batch.location != None:
        location = batch.location.name

    card = card.replace("@@SerialNumber", "")
    card = card.replace("@@InsuranceNumber", insuree_number.insuree_number)
    card = card.replace("@@Location", location)
    card = card.replace(
        "@@QRCode", qr_code_stream.getvalue().decode().replace("<?xml version='1.0' encoding='UTF-8'?>", "")
        .replace("width=\"21mm\" height=\"21mm\"", "width=\"100%\" viewBox=\"0 0 100 100\""))

    return card


def merge_svgs(card_folder, abs_path, batchid):
    doc = ss.Document()
    all_svgs = [f for f in glob.glob(F'{card_folder}/*.svg')]

    layout1 = ss.VBoxLayout()
    layout1.setSpacing(10)
    counter = 0
    images_on_page = int(InsureeBatchConfig.images_on_page or 1)
    image_counter = 1
    merged_list = []

    if (images_on_page > 1):
        for file in all_svgs:

            layout1.addSVG(file, alignment=ss.AlignCenter)
            counter = counter + 1

            if (counter == images_on_page or all_svgs.index(file) == len(all_svgs) - 1):
                counter = 0
                doc.setLayout(layout1)
                filename = F'{abs_path}/cards/{batchid}/{image_counter}.svg'
                merged_list.append(filename)
                doc.save(filename)
                image_counter = image_counter + 1

                layout1 = ss.VBoxLayout()
                layout1.setSpacing(10)
    else:
        merged_list = all_svgs

    return merged_list


def write_pdf(svg_list):
    inscape_path = InsureeBatchConfig.inscape_path

    for merged_image in svg_list:
        pdf_abspath = merged_image.split('.')[0]
        p = subprocess.run([
            inscape_path + 'inkscape', '--without-gui',  '--export-area-drawing', merged_image,  '--export-pdf', F'{pdf_abspath}' + '.pdf'])


def merge_pdfs(source_path, destination_path, filename):
    merged_object = PdfFileMerger()

    all_pdfs = [f for f in glob.glob(F'{source_path}/*.pdf')]

    for pdf in all_pdfs:
        merged_object.append(PdfFileReader(pdf, 'rb'))

    merged_object.write(F'{destination_path}/{filename}.pdf')


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
