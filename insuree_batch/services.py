import base64
import csv
import logging
import os
import random
import shutil
import tempfile
import zipfile
from datetime import datetime
from functools import lru_cache

from django.conf import settings
from django.db.models import Max
from django.db.models.functions import Length

from insuree.apps import InsureeConfig
from insuree.models import Insuree
from location.models import Location
from .models import InsureeBatch, BatchInsureeNumber

logger = logging.getLogger(__file__)


def generate_insuree_numbers(amount, audit_user_id, location=None, comment=None):
    batch = InsureeBatch.objects.create(
        location=location,
        audit_user_id=audit_user_id,
        archived=False,
        comment=comment,
    )

    for i in range(1, amount + 1):
        for retry in range(1, 10000):
            insuree_number = generate_insuree_number(location=location)
            if not Insuree.objects.filter(chf_id=insuree_number).exists() \
                    and not BatchInsureeNumber.objects.filter(insuree_number=insuree_number).exists():
                break
        else:
            logger.error("Could not generate an insuree id after 10000 attempts.")
            raise Exception("Could not generate an insuree id after 10000 attempts.")
        BatchInsureeNumber.objects.create(
            batch=batch,
            insuree_number=insuree_number,
        )
    return batch


# noinspection PyStringFormat
def generate_insuree_number(location=None):
    length = InsureeConfig.get_insuree_number_length()
    modulo = InsureeConfig.get_insuree_number_modulo_root()
    if length is None or modulo is None:
        logging.warning("The settings do not specify an insuree number length. This normally means that they are not "
                        "validated by openIMIS. However, this doesn't make sense when generating insuree numbers. "
                        "We are using 9 and 7 as default values but you should configure these in the settings")
        length = 9
        modulo = 7
    modulo_len = len(str(modulo))

    if location:
        try:
            main_number = int(location.code) * (10 ** (length - modulo_len - get_location_id_len(location.type))) \
                          + get_random(length - get_location_id_len(location.type) - modulo_len)
        except ValueError:
            logger.error("Computing a QR code with a location that is not numeric will fail its modulo")
            raise
    else:
        main_number = get_random(length - modulo_len)
    checksum = main_number % modulo
    # generates "%010d" that is then formatted with the actual insuree number. This confuses the IDE => noinspection
    padded_main = f"%0{length - modulo_len}d" % main_number
    padded_checksum = f"%0{modulo_len}d" % checksum
    return f"{padded_main}{padded_checksum}"


def get_random(length):
    return random.randint(10 ** (length - 1), (10 ** length) - 1)


@lru_cache(maxsize=None)
def get_location_id_len(location_type):
    """
    Determines the length of the location code and saves it in cache for performance
    :return: length of the biggest Location.code
    """
    return Location.objects.filter(type=location_type, validity_to__isnull=True)\
        .annotate(code_len=Length("code"))\
        .aggregate(max_len=Max("code_len"))["max_len"]


def export_insurees(batch=None, amount=None, dry_run=False):
    to_export = get_insurees_to_export(batch, amount)
    if to_export is None:
        return None
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        csv_file_path = os.path.join(tmp_dir_name, "index.csv")
        with open(csv_file_path, 'w') as f:
            # create the csv writer
            writer = csv.writer(f)
            writer.writerow([
                "InsureeNum", "OtherNames", "LastName", "DateOfBirth", "Gender", "Phone", "EffectiveDate",
                "ValidityDate", "VillageCode", "VillageName", "WardCode", "WardName", "DistrictCode", "DistrictName",
                "RegionCode", "RegionName", "Filename", "Error"
            ])
            files_to_zip = [(csv_file_path, "index.csv")]
            zip_file_path = tempfile.NamedTemporaryFile("wb", prefix="insuree_export", suffix=".zip", delete=False)

            for insuree in to_export:
                from core import datetimedelta
                latest_policy = insuree\
                    .insuree_policies\
                    .filter(validity_to__isnull=True)\
                    .order_by("-effective_date")\
                    .first()
                if not latest_policy:
                    logger.debug(f"Insuree {insuree.chf_id} has no policy, skipping")
                    continue
                if not insuree.family:
                    logger.debug(f"Insuree {insuree.chf_id} has no family, skipping")
                    continue
                village = insuree.family.location
                ward = village.parent if village else None
                district = ward.parent if ward else None
                region = district.parent if district else None

                if insuree.photo and (insuree.photo.photo or insuree.photo.filename):
                    photo_filename = os.path.join(tmp_dir_name, f"{insuree.chf_id}.jpg")
                else:
                    photo_filename = None

                # TODO Make the validity and date formats configurable
                row_to_write = [
                    insuree.chf_id,
                    insuree.other_names,
                    insuree.last_name,
                    insuree.dob.strftime('%d/%m/%Y') if insuree.dob else None,
                    insuree.gender_id,
                    insuree.phone,
                    latest_policy.effective_date.strftime('%d/%m/%Y')
                    if latest_policy and latest_policy.effective_date else None,
                    (latest_policy.effective_date + datetimedelta(years=2)).strftime('%d/%m/%Y')
                    if latest_policy and latest_policy.effective_date else None,
                    village.code,
                    village.name,
                    ward.code,
                    ward.name,
                    district.code,
                    district.name,
                    region.code,
                    region.name,
                    f"{insuree.chf_id}.jpg" if photo_filename else None,
                    ""
                ]

                if photo_filename:
                    if insuree.photo.photo:
                        with open(photo_filename, "wb") as photo_file:
                            photo_bytes = insuree.photo.photo.encode("utf-8")
                            decoded_photo = base64.decodebytes(photo_bytes)
                            photo_file.write(decoded_photo)
                        files_to_zip.append((photo_filename, f"{insuree.chf_id}.jpg"))
                    elif insuree.photo.filename:
                        # After 2022-10 release gets out, this whole block should be this sole line:
                        # shutil.copyfile(insuree.photo.full_file_path(), photo_filename)
                        # But we are missing some deps for Niger, so we reimplement a custom version until then
                        photo_root_path = os.getenv("PHOTO_ROOT_PATH", None)
                        if not photo_root_path:
                            logger.error("PHOTO_ROOT_PATH is not configured, please set it up")
                        else:
                            full_path = os.path.join(
                                photo_root_path,
                                insuree.photo.folder if insuree.photo.folder else "",
                                insuree.photo.filename)
                            try:
                                shutil.copyfile(full_path, photo_filename)
                                files_to_zip.append((photo_filename, f"{insuree.chf_id}.jpg"))
                            except Exception as exc:
                                row_to_write[-2] = ""
                                row_to_write[-1] = f"Could not copy file {full_path}: {exc}"
                    else:
                        logger.warning("Photo was identified but neither base64 photo nor filename")
                writer.writerow(row_to_write)
        if not dry_run:
            BatchInsureeNumber.objects\
                .filter(insuree_number__in=[i.chf_id for i in to_export])\
                .update(print_date=datetime.now())

        zf = zipfile.ZipFile(zip_file_path, "w")
        for file in files_to_zip:
            zf.write(file[0], file[1])
        zf.close()
        return zip_file_path


def get_insurees_to_export(batch, amount):
    # Since there is no foreign key from the batch to insuree, Django refuses to make a join or subquery 🤷🏻‍
    if hasattr(settings, "DB_ENGINE") and "postgres" in settings.DB_ENGINE:
        engine = "postgres"
    else:
        engine = "mssql"
    sql = 'select ' + (f"TOP {int(amount)}" if amount and engine == "mssql" else "") + \
          ' "tblInsuree".* ' \
          'from "tblInsuree" ' \
          'inner join insuree_batch_batchinsureenumber ibb on "tblInsuree"."CHFID" = ibb."CHFID" ' \
          'where ibb.print_date is null '
    params = []
    if batch:
        sql = sql + " and ibb.batch_id=%s"
        params.append(str(batch.id).replace("-", ""))

    if amount and engine == "postgres":
        sql += f" LIMIT {int(amount)}"

    queryset = Insuree.objects.raw(sql, params)
    return queryset
