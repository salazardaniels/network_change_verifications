"""
config_verifications.py
Verify configurations are as expected.
"""

__author__ = "Daniel Salazar"
__copyright__ = "Copyright (c) 2022, Daniel Salazar"
__contact__ = ["salazardaniels@gmail.com"]
__license__ = "MIT License"
__credits__ = ["Daniel Salazar"]
__version__ = 1.0

import logging
import os
import sys
import json

from pyats import aetest
from genie.testbed import load
from genie.utils.diff import Diff
from genie.utils import Dq
from genie.utils.config import Config
from unicon.core.errors import TimeoutError, StateMachineError, ConnectionError


# create a logger for this module
logger = logging.getLogger(__name__)


class CommonSetup(aetest.CommonSetup):
    # unwanted keys to delete from config
    keys_regex_to_delete_from_config = ( r'\S{3} \S{3} \d{1,2} \d{1,2}:\d{1,2}:\d{1,2}\.\d{1,3} \S{3}',
                                r'\!\!\d{1,2}:\d{1,2}:\d{1,2} \S{3} \S{3} \S{3} \d{1,2} \d{4,}'
                            )

    @aetest.subsection
    def verify_pre_directory(self, pre, post):
        """
        verify pre verifications report directory exist
        """
        if not post:
            self.skipped("No need to check if pre verification report directory exist during pre verifications")
        else:
            if os.path.exists(pre):
                self.passed(f"Pre verifications Report directory {pre} exists!")
            else:
                self.failed(f"Pre verifications Report directory {pre} does not exists!")


    @aetest.subsection
    def create_report_directory(self, pre, post):
        """
        create report directory
        """

        # where verification stage is pre or post
        if pre and post:
            report_directory = post
        elif pre:
            report_directory = pre
        
        # create report_directory if it does not exist
        if os.path.exists(report_directory):
            # To store the pre-existence status of the report directory
            self.report_directory_alredy_exist = True
            self.skipped(f"Report directory {report_directory} already exists.")
        else:
            # To store the pre-existence status of the report directory
            self.report_directory_alredy_exist = False
            try:
                os.mkdir(report_directory)
            except:
                self.failed(f"There was an error while trying to create report directory {report_directory}")
            self.passed(f"Report directory {report_directory} created successfully")


    @aetest.subsection
    def connect(self, testbed):
        """
        establishes connection to all your testbed devices.
        """
        # skipp the task if the report_directory_alredy_exist and the test case is in standalone execution
        if self.report_directory_alredy_exist and __name__ == "__main__":
            self.skipped("Don't need to connect if the report_directory_alredy_exist and the test case is in standalone execution.")

        # make sure testbed is provided
        assert testbed, "Testbed is not provided!"

        # connect to all testbed devices
        #   By default ANY error in the CommonSetup will fail the entire test run
        #   Here we catch common exceptions if a device is unavailable to allow test to continue
        try:
            testbed.connect()
        except (TimeoutError, StateMachineError, ConnectionError):
            logger.error("Unable to connect to all devices")

    @aetest.subsection
    def learn_configs(self, testbed, steps, pre, post):
        """Learn and save configurations on the testbed devices."""
        # skipp the task if the report_directory_alredy_exist and the test case is in in standalone execution
        if self.report_directory_alredy_exist and __name__ == "__main__":
            self.skipped("Don't need to learn config feature if the report_directory_alredy_exist and the test case is executed as standalone.")

        # Types of configs to learn
        config_types = { "config_running": "show running-config",
                    "config_failed": "show configuration failed",
                    "config_failed_startup": "show configuration failed startup"
                    }

        # where verification stage is pre or post
        if pre and post:
            report_directory = post
        elif pre:
            report_directory = pre

        # loop over every device in testbed
        for device_name, device in testbed.devices.items():
            logger.info(f"{device_name} connected status: {device.connected}")
            logger.info(f"Learning Configs for {device_name}")
            # loop over every config type
            for config_type in config_types:
                # create new steps contects for each config type
                with steps.start(
                    f"Learning config_type: {config_type}  for device: {device_name}", continue_=True
                ) as config_type_step:
                    # Try  to learn configs on supported network operation systems
                    try:
                        # execute show config commad for config type and tokenize it
                        config_str = device.execute(config_types[config_type])
                        config_tree = Config(config_str)
                        config_tree.tree()
                        # delete unwanted keys
                        for key_regex_to_delete in self.keys_regex_to_delete_from_config:
                                t = tuple(Dq(config_tree.config).contains(key_regex_to_delete, regex=True).reconstruct())
                                if t:
                                    k = t[0]
                                    del config_tree.config[k]
                        # dump the config tree to json file
                        with open(os.path.join(report_directory, f"{device_name}_{config_type}.json"), "w") as f:
                            json.dump(config_tree.config, f ,sort_keys=True, indent=4)
                    except:
                        config_type_step.skipped(f"Coudn't learn config_type: {config_type}  for device: {device_name}.")
                    config_type_step.passed(f"Successfully learned config_type: {config_type}  for device: {device_name}.")

class compare_pre_post_config(aetest.Testcase):
    """compare_pre_post_config
    < docstring description of this testcase >
    """
    # Types of configs to learn
    config_types = {    "config_running": "show running-config",
                        "config_failed": "show configuration failed",
                        "config_failed_startup": "show configuration failed startup"
                    }

    @aetest.setup
    def setup(self, testbed, steps, pre, post):
        """Read the learned configurations from json file for every the testbed devices."""

        # where verification stage is pre or post
        if pre and post:
            report_directory = post
        elif pre:
            report_directory = pre

        # dicts to store device config information
        self.learnt_config = {}
        self.pre_learnt_config = {}

        # loop over every device
        for device_name in testbed.devices.keys():
            # prepare dicts
            self.learnt_config[device_name] = {}
            self.pre_learnt_config[device_name] = {}

            # Trye to read pre learned config information
            with steps.start(
                f"Reding pre saved configs from {device_name}", continue_=True
            ) as device_step:

                # loop over every config type
                for config_type in self.config_types:
                    with device_step.start(
                        f"Reding config_type: {config_type}, from device: {device_name}", continue_=True
                    ) as config_type_step:
                        try:
                            # read learned configs
                            with open(os.path.join(report_directory, f"{device_name}_{config_type}.json"), "r") as f:
                                # fill dict with loaded json data
                                self.learnt_config[device_name][config_type] = json.loads(f.read())
                            if post:
                                # read pre learned configs
                                with open(os.path.join(pre, f"{device_name}_{config_type}.json"), "r") as f:
                                    # fill dict with loaded json data
                                    self.pre_learnt_config[device_name][config_type] = json.loads(f.read())
                        except:
                            device_step.failed(f"Unable to read config information for device {device_name} from {device_name}_config.json file")

    @aetest.test
    def compare_pre_post_configs_running(self, testbed, steps, pre, post):
        """Compare the pre and post configurations learned from json file for every the testbed devices."""
        # only compare configs if in post stage
        if post and pre:
            # loop over every device
            for device_name in testbed.devices.keys():
                # Trye to read pre learned config information
                with steps.start(
                    f"Comparing pre and post config running on device {device_name}.", continue_=True
                ) as device_step:
                    # crete diff object to find difference between pre and post configs
                    dd = Diff(self.pre_learnt_config[device_name]["config_running"], self.learnt_config[device_name]["config_running"])
                    dd.findDiff()
                    if dd.diffs:
                        device_step.failed("The folowing differences between pre and post configurations were found: {dd.diffs}.")
                    else:
                        device_step.passed("Pre and Post configurations are the same.")
        else:
            self.skipped("There is no need to compare Pre and Post config during Pre-Check verifications.")

    @aetest.test
    def check_failed_configs(self, testbed, steps):
        """Verify if there are failed configs."""
        # failed configs types
        failed_configs_keys = ("config_failed", "config_failed_startup")

        # loop over every device
        for device_name in testbed.devices.keys():
            # Try to read pre learned config information
            with steps.start(
                f"Comparing pre and post config running on device {device_name}.", continue_=True
            ) as device_step:
                
                # loop over failed configs types
                for failed_config_key in failed_configs_keys:
                    with device_step.start(
                        f"Checking if there are {failed_config_key} failed configurations on device: {device_name}.", continue_=True
                    ) as failed_config_step:
                        #check if there is failed configs   
                        if failed_config_key in self.learnt_config[device_name]:
                            if self.learnt_config[device_name][failed_config_key]:
                                failed_config_step.failed(f"The following {failed_config_key} failed configurations were found on device {device_name}: {self.learnt_config[device_name][failed_config_key]}")
                        else:
                            device_step.passed(f"No {failed_config_key} failed configurations found on device {device_name}")


class CommonCleanup(aetest.CommonCleanup):
    """CommonCleanup Section
    < common cleanup docstring >
    """

    @aetest.subsection
    def disconnect(self, testbed):
        """
        disconnects from all your testbed devices.
        """
        # make sure testbed is provided
        assert testbed, "Testbed is not provided!"

        # disconnect from all testbed devices
        logger.info(
            "Disconnecting from all testbed devices"
        )
        testbed.disconnect()


if __name__ == "__main__":
    # for stand-alone execution
    import sys
    import argparse
    from pyats.topology.loader import load

    # from genie.conf import Genie

    parser = argparse.ArgumentParser(description="standalone parser")
    parser.add_argument(
        "--testbed",
        dest="testbed",
        help="testbed YAML file",
        type=load,
        # type=Genie.init,
        default=None,
    )
    parser.add_argument(
        "--pre",
        dest="pre",
        help="pre verification directory name",
        type=str,
        # type=Genie.init,
        default=None,
    )
    parser.add_argument(
        "--post",
        dest="post",
        help="pre verification directory name",
        type=str,
        # type=Genie.init,
        default=None,
    )

    # do the parsing
    args, sys.argv[1:] = parser.parse_known_args(sys.argv[1:])

    aetest.main(testbed=args.testbed, pre=args.pre, post=args.post)