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
import re

from pyats import aetest
from genie.testbed import load
from genie.utils.diff import Diff
from genie.utils import Dq
from unicon.core.errors import TimeoutError, StateMachineError, ConnectionError


# create a logger for this module
logger = logging.getLogger(__name__)


class CommonSetup(aetest.CommonSetup):
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
        # skipp the task if the report_directory_alredy_exist
        if self.report_directory_alredy_exist:
            self.skipped("Don't need to near interface feature if the report_directory_alredy_exist ")

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
    def learn_config(self, testbed, pre, post):
        """Learn and save the current configuration the testbed devices."""

        # skipp the task if the report_directory_alredy_exist
        if self.report_directory_alredy_exist:
            self.skipped("Don't need to near interface feature if the report_directory_alredy_exist ")

        # where verification stage is pre or post
        if pre and post:
            report_directory = post
        elif pre:
            report_directory = pre

        # create a dic to store config per device
        learnt_config = {}
        for device_name, device in testbed.devices.items():
            # Only attempt to learn details on supported network operation systems
            if device.os in ("ios", "iosxe", "iosxr", "nxos"):
                logger.info(f"{device_name} connected status: {device.connected}")
                logger.info(f"Learning Config for {device_name}")
                learnt_config[device_name] = device.learn("config")
                with open(os.path.join(report_directory, f"{device_name}_config.json"), "w") as f:
                    json.dump(learnt_config[device_name], f ,sort_keys=True, indent=4)


class compare_pre_post_config(aetest.Testcase):
    """compare_pre_post_config
    < docstring description of this testcase >
    """
    @aetest.setup
    def setup(self, testbed, steps, pre, post):
        """Read the learned configurations from json file for every the testbed devices."""
        # dicts to store device config information
        if post and pre:
            self.learnt_config = {}
            self.pre_learnt_config = {}
            # loop over every device
            for device_name in testbed.devices.keys():
                # Trye to read pre learned config information
                with steps.start(
                    f"Reding pre saved config from json files for {device_name}", continue_=True
                ) as device_step:
                    try:
                        with open(os.path.join(post, f"{device_name}_config.json"), "r") as f:
                            self.learnt_config[device_name] = json.loads(f.read())
                        with open(os.path.join(pre, f"{device_name}_config.json"), "r") as f:
                            self.pre_learnt_config[device_name] = json.loads(f.read())
                    except:
                        device_step.failed(f"Unable to read config information for device {device_name} from {device_name}_config.json file")
        else:
            self.skipped("There is no need to compare Pre and Post config during Pre-Check verifications.")

    @aetest.test
    def compare_pre_post_config(self, testbed, steps, pre, post):
        """Compare the pre and post configurations learned from json file for every the testbed devices."""
        # unwanted keys to delete from config
        keys_regex_to_delete = ( r'\S{3} \S{3} \d{1,2} \d{1,2}:\d{1,2}:\d{1,2}\.\d{1,3} \S{3}',
                                 r'\!\!\d{1,2}:\d{1,2}:\d{1,2} \S{3} \S{3} \S{3} \d{1,2} \d{4,}'
                                )
        if post and pre:
            # loop over every device
            for device_name in testbed.devices.keys():
                # Trye to read pre learned config information
                with steps.start(
                    f"Comparing pre and post config for device {device_name}.", continue_=True
                ) as device_step:
                    # delete unwanted keys
                    for key_regex_to_delete in keys_regex_to_delete:
                        for config in (self.learnt_config, self.pre_learnt_config):
                            t = tuple(Dq(config).contains(key_regex_to_delete, regex=True).reconstruct())
                            if t:
                                k = t[0]
                                del config[k]
                    # crete diff object to find difference between pre and post configs
                    dd = Diff(self.pre_learnt_config, self.learnt_config)
                    dd.findDiff()
                    if dd.diffs:
                        device_step.failed("The folowing differences between pre and post configurations were found: {dd.diffs}.")
                    else:
                        device_step.passed("Pre and Post configurations are the same.")
        else:
            self.skipped("There is no need to compare Pre and Post config during Pre-Check verifications.")


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