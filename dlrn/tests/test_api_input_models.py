# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from dlrn.api.inputs.agg_status import AggStatusInput
from dlrn.api.inputs.last_tested_repo import LastTestedRepoInput
from dlrn.api.inputs.last_tested_repo import LastTestedRepoInputPost
from dlrn.api.inputs.metrics import MetricsInput
from dlrn.api.inputs.promotions import MAX_LIMIT
from dlrn.api.inputs.promotions import PromotionsInput
from dlrn.api.inputs.repo_status import RepoStatusInput
from dlrn.api.inputs.report_result import ReportResultInput
from dlrn.api.utils import InvalidUsage
from dlrn.tests import base

from pydantic import ValidationError


class TestRepoStatusInput(base.TestCase):

    def test_valid_input(self):
        input_obj = dict(commit_hash="93eee77657978547f5fad1cb8cd30b570da83e",
                         distro_hash="008678d7b0e20fbae185f2bb1bd0d9d1675862")
        assert isinstance(RepoStatusInput(**input_obj), RepoStatusInput)

    def test_invalid_input(self):
        valid_hash = "93eee77657978547f5fad1cb8cd30b570da83e"
        invalid_input_obj1 = dict(commit_hash=valid_hash, distro_hash=123,
                                  extended_hash=valid_hash)
        invalid_input_obj2 = dict(commit_hash=123, distro_hash=valid_hash,
                                  extended_hash=valid_hash)
        invalid_input_obj3 = dict(commit_hash=valid_hash,
                                  distro_hash=valid_hash, extended_hash=123)
        invalid_input_obj4 = dict(commit_hash=valid_hash, success=4,
                                  extended_hash=valid_hash,
                                  distro_hash=valid_hash)
        input_array = [invalid_input_obj1, invalid_input_obj2,
                       invalid_input_obj3, invalid_input_obj4]
        for input_obj in input_array:
            self.assertRaises(ValueError, RepoStatusInput, **input_obj)


class TestAggStatusInput(base.TestCase):

    def test_valid_input(self):
        input_obj = dict(aggregate_hash="93eee77657978547f5fad1cb8cd30b570da")
        assert isinstance(AggStatusInput(**input_obj), AggStatusInput)

    def test_invalid_input(self):
        valid_hash = "93eee77657978547f5fad1cb8cd30b570da"
        invalid_input_obj1 = dict(aggregate_hash=123)
        invalid_input_obj2 = dict(aggregate_hash=valid_hash, success=10)
        input_array = [invalid_input_obj1, invalid_input_obj2]
        for input_obj in input_array:
            self.assertRaises(ValueError, AggStatusInput, **input_obj)


class TestLastTestedRepo(base.TestCase):

    def test_minimum_valid_input(self):
        input_obj = dict(max_age="1")
        assert isinstance(LastTestedRepoInput(**input_obj),
                          LastTestedRepoInput)

    def test_valid_input(self):
        input_obj = dict(max_age="1", success="True", job_id="Job_name_1",
                         sequential_mode="1", previous_job_id="prev_name_1",
                         component="component")
        assert isinstance(LastTestedRepoInput(**input_obj),
                          LastTestedRepoInput)

    def test_invalid_max_age(self):
        input_obj = dict(max_age="-1")
        self.assertRaises(InvalidUsage, LastTestedRepoInput, **input_obj)

    def test_valid_post_input(self):
        input_obj = dict(max_age="1", reporting_job_id="Test_job")
        assert isinstance(LastTestedRepoInputPost(**input_obj),
                          LastTestedRepoInputPost)

    def test_invalid_reporting_job_id(self):
        input_obj = dict(max_age="1", reporting_job_id=123)
        self.assertRaises(ValueError, LastTestedRepoInputPost, **input_obj)


class TestPromotions(base.TestCase):

    def test_minimum_valid_input(self):
        assert isinstance(PromotionsInput(), PromotionsInput)

    def test_valid_input(self):
        input_obj = dict(commit_hash="hash1", distro_hash="hash2",
                         extended_hash="hash3", aggregated_hash="hash4",
                         promote_name="promote_name", offset="10", limit="12",
                         component="component")
        assert isinstance(PromotionsInput(**input_obj), PromotionsInput)

    def test_max_limit(self):
        input_obj = dict(limit="999999")
        promotion_input = PromotionsInput(**input_obj)
        assert promotion_input.limit == MAX_LIMIT
        assert isinstance(promotion_input, PromotionsInput)

    def test_invalid_input(self):
        invalid_input_obj1 = dict(distro_hash=1, commit_hash=2)
        invalid_input_obj2 = dict(extended_hash=1)
        invalid_input_obj3 = dict(aggregate_hash=1)
        invalid_input_obj4 = dict(max_age="1", component=13221)
        invalid_input_obj5 = dict(promote_name=1)
        invalid_input_obj6 = dict(offset="-1", limit="0")
        invalid_input_obj7 = dict(limit="-1", offset="0")

        invalid_input_objs = [invalid_input_obj1, invalid_input_obj2,
                              invalid_input_obj3, invalid_input_obj4,
                              invalid_input_obj5, invalid_input_obj6,
                              invalid_input_obj7]
        for input_obj in invalid_input_objs:
            self.assertRaises(ValueError, PromotionsInput, **input_obj)

    def test_invalid_distro_commit_hashes(self):
        valid_hash = "93eee77657978547f5fad1cb8cd30b570da83e"
        invalid_input_obj1 = dict(distro_hash=valid_hash)
        invalid_input_obj2 = dict(commit_hash=valid_hash)
        input_array = [invalid_input_obj1, invalid_input_obj2]
        for input_obj in input_array:
            self.assertRaises(InvalidUsage, PromotionsInput, **input_obj)

    def test_invalid_offset(self):
        input_obj = dict(commit_hash="hash1", distro_hash="hash2",
                         extended_hash="hash3", aggregated_hash="hash4",
                         promote_name="promote_name", offset="-10", limit="12",
                         component="component")
        self.assertRaises(ValidationError, PromotionsInput, **input_obj)


class TestMetrics(base.TestCase):

    def test_valid_input(self):
        input_obj_1 = dict(start_date="2024-04-30", end_date="2024-07-04",
                           package_name="test_package")
        input_obj_2 = dict(start_date="2024-04-30", end_date="2024-07-04")
        for input_obj in [input_obj_1, input_obj_2]:
            assert isinstance(MetricsInput(**input_obj), MetricsInput)

    def test_invalid_input(self):
        wrong_date = "30-04-2024"
        invalid_input_obj1 = dict(start_date=wrong_date,
                                  end_date="2024-07-04",
                                  package_name="test_package")
        invalid_input_obj2 = dict(start_date="2024-04-30",
                                  end_date=wrong_date)
        invalid_input_obj3 = dict(start_date="2024-04-30",
                                  end_date="2024-07-04",
                                  package_name=23)
        input_objects = [invalid_input_obj1, invalid_input_obj2,
                         invalid_input_obj3]
        for invalid_input in input_objects:
            self.assertRaises((InvalidUsage, ValidationError), MetricsInput,
                              **invalid_input)


class TestReportResult(base.TestCase):
    timestamp = "1720545985473"
    success = "True"
    job_id = "Job_id"
    url = ""
    commit_hash = "commit_hash"
    distro_hash = "distro_hash"
    extended_hash = "extended_hash"
    aggregate_hash = "agg_hash"
    notes = ""
    base_valid_object = dict(timestamp=timestamp, success=success,
                             job_id=job_id, url=url, notes=notes)

    def test_valid_input(self):

        input_obj_1 = dict(commit_hash=self.commit_hash,
                           distro_hash=self.distro_hash,
                           extended_hash=self.extended_hash)
        input_obj_1.update(self.base_valid_object)
        input_obj_2 = dict(aggregate_hash=self.aggregate_hash,
                           extended_hash=self.extended_hash)
        input_obj_2.update(self.base_valid_object)
        input_obj_3 = dict(commit_hash=self.commit_hash,
                           distro_hash=self.distro_hash)
        input_obj_3.update(self.base_valid_object)
        del input_obj_3["notes"]
        input_obj_4 = dict(aggregate_hash=self.aggregate_hash)
        input_obj_4.update(self.base_valid_object)
        del input_obj_4["notes"]
        input_objects = [input_obj_1, input_obj_2, input_obj_3, input_obj_4]

        for input_obj in input_objects:
            assert isinstance(ReportResultInput(**input_obj),
                              ReportResultInput)

    def test_invalid_hash_logic(self):
        input_objects = []
        input_obj_1 = dict(commit_hash=self.commit_hash,
                           distro_hash=self.distro_hash,
                           aggregate_hash=self.aggregate_hash)
        input_obj_1.update(self.base_valid_object)
        input_objects.append(input_obj_1)

        input_obj_2 = dict(commit_hash=self.commit_hash)
        input_obj_2.update(self.base_valid_object)
        input_objects.append(input_obj_2)

        input_obj_3 = dict(distro_hash=self.distro_hash)
        input_obj_3.update(self.base_valid_object)
        input_objects.append(input_obj_3)

        input_obj_4 = dict(distro_hash=self.distro_hash,
                           aggregate_hash=self.aggregate_hash)
        input_obj_4.update(self.base_valid_object)
        input_objects.append(input_obj_4)

        input_obj_5 = dict(commit_hash=self.commit_hash,
                           aggregate_hash=self.aggregate_hash)
        input_obj_5.update(self.base_valid_object)
        input_objects.append(input_obj_5)

        for input_obj in input_objects:
            self.assertRaises(InvalidUsage, ReportResultInput, **input_obj)

    def test_invalid_input(self):
        input_objects = []
        for element in ["url", "success", "job_id", "timestamp"]:
            iterative_dict = dict(aggregate_hash=self.aggregate_hash)
            iterative_dict.update(self.base_valid_object)
            del iterative_dict[element]
            input_objects.append(iterative_dict)
        for input_object in input_objects:
            self.assertRaises(ValidationError, ReportResultInput,
                              **input_object)
