import random
from unittest import TestCase

from core.models import Officer
from insuree.apps import InsureeConfig
from insuree.services import validate_insuree_number
from insuree.test_helpers import create_test_insuree, create_test_photo
from location.models import Location
from .services import get_random, generate_insuree_number, generate_insuree_numbers, get_insurees_to_export, \
    export_insurees


class InsureeBatchTest(TestCase):
    # def setUp(self) -> None:
    #     self.i_user = InteractiveUser(
    #         login_name="test_batch_run", audit_user_id=-1, id=97891
    #     )
    #     self.user = User(i_user=self.i_user)

    def test_generate_insuree_number(self):
        expected_length = InsureeConfig.get_insuree_number_length()
        random.seed(10)
        no_loc = generate_insuree_number()
        self.assertEqual(len(no_loc), expected_length)
        self.assertEqual(validate_insuree_number(no_loc), [])

        test_location = Location.objects.filter(validity_to__isnull=True).first()
        self.assertIsNotNone(test_location, "This test expects some locations to exist in DB.")
        loc = generate_insuree_number(test_location)
        self.assertEqual(len(loc), expected_length)
        self.assertEqual(validate_insuree_number(loc), [])
        self.assertTrue(loc.startswith(f"{test_location.id:02}"))
        self.assertEqual(loc, "011341676")
        random.seed()

    def test_random(self):
        for i in range(1, 10000):
            num = get_random(4)
            self.assertGreaterEqual(num, 1000)
            self.assertLessEqual(num, 9999)

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
        zip = export_insurees(batch=batch)
        self.assertIsNotNone(zip)
        # TODO check the zip file in depth

        for insuree in insurees:
            insuree.delete()
        batch.delete()
