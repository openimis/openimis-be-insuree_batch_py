import random
from django.test import TestCase, override_settings

from core.models import Officer
from insuree.apps import InsureeConfig
from insuree.services import validate_insuree_number
from insuree.test_helpers import create_test_insuree, create_test_photo
from location.models import Location
from location.test_helpers import create_test_location
from .services import get_random, generate_insuree_number, generate_insuree_numbers, get_insurees_to_export, \
    export_insurees, get_location_id_len


class InsureeBatchTest(TestCase):
    def setUp(self) -> None:
        self.test_location = create_test_location("D", valid=True, custom_props={"code": "99"})

    def tearDown(self) -> None:
        self.test_location.delete()

    @override_settings(INSUREE_NUMBER_LENGTH='9', INSUREE_NUMBER_MODULE_ROOT='7')
    def test_generate_insuree_number(self):
        expected_length = InsureeConfig.get_insuree_number_length()
        self.assertEqual(expected_length, 9)  # Forced in annotation
        random.seed(10)
        no_loc = generate_insuree_number()
        self.assertEqual(len(no_loc), expected_length)
        self.assertEqual(validate_insuree_number(no_loc), [])

        self.assertIsNotNone(self.test_location, "This test expects some locations to exist in DB.")
        loc = generate_insuree_number(self.test_location)
        self.assertEqual(len(loc), expected_length)
        self.assertEqual(validate_insuree_number(loc), [])
        self.assertTrue(loc.startswith(f"{int(self.test_location.code):04}"))
        self.assertEqual(loc, "009915334")
        random.seed()

    def test_get_location_id_length(self):
        long_location = create_test_location("D", valid=False, custom_props={"code": "2356575"})
        length = get_location_id_len("D")
        self.assertEqual(length, 4)
        length = get_location_id_len("W")
        self.assertEqual(length, 6)
        long_location.delete()

    def test_random(self):
        for i in range(1, 10000):
            num = get_random(4)
            self.assertGreaterEqual(num, 1000)
            self.assertLessEqual(num, 9999)

    @override_settings(INSUREE_NUMBER_LENGTH='10', INSUREE_NUMBER_MODULE_ROOT='7')
    def test_generate_batch(self):
        random.seed(10)
        test_location = Location.objects.filter(validity_to__isnull=True).order_by("-id").first()
        batch = generate_insuree_numbers(100, 1, test_location, "Test comment")
        self.assertIsNotNone(batch)
        self.assertEqual(batch.location, test_location)
        self.assertEqual(batch.comment, "Test comment")
        self.assertEqual(batch.audit_user_id, 1)
        self.assertEqual(batch.insuree_numbers.count(), 100)
        batch.delete()

    @override_settings(INSUREE_NUMBER_LENGTH='10', INSUREE_NUMBER_MODULE_ROOT='7')
    def test_get_insurees_to_export(self):
        random.seed(11)
        test_location = Location.objects.filter(validity_to__isnull=True).order_by("-id").first()
        batch = generate_insuree_numbers(10, 1, test_location, "Test comment")
        batch_insurees = batch.insuree_numbers.all()[0:3]
        insurees = []
        for batch_insuree in batch_insurees:
            insurees.append(create_test_insuree(with_family=True,
                                                custom_props={"chf_id": batch_insuree.insuree_number}))

        # Limit to less than available
        result = get_insurees_to_export(batch, 2)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        # Limit is beyond
        result = get_insurees_to_export(batch, 5)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)
        for insuree in insurees:
            self.assertIn(insuree, result)
            insuree.delete()
        batch.delete()

    @override_settings(INSUREE_NUMBER_LENGTH='10', INSUREE_NUMBER_MODULE_ROOT='7')
    def test_export(self):
        random.seed(12)
        test_location = Location.objects.filter(validity_to__isnull=True).order_by("-id").first()
        test_officer = Officer.objects.filter(validity_to__isnull=True).order_by("-id").first()
        batch = generate_insuree_numbers(10, 1, test_location, "Test comment")
        batch_insurees = batch.insuree_numbers.all()[0:3]
        insurees = []
        for batch_insuree in batch_insurees:
            temp_ins = create_test_insuree(with_family=True,
                                           custom_props={"chf_id": batch_insuree.insuree_number})
            insurees.append(temp_ins)
            photo = create_test_photo(insuree_id=temp_ins.id, officer_id=test_officer.id)
            temp_ins.photo_id = photo.id
            temp_ins.save()
        # Limit to less than available
        zip_file = export_insurees(batch=batch)
        self.assertIsNotNone(zip_file)
        # TODO check the zip file in depth

        for insuree in insurees:
            insuree.delete()
        batch.delete()
