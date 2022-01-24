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
from common_setup_cleanup import CommonSetup as base_CommonSetup
from common_setup_cleanup import CommonCleanup as base_CommonCleanup


# create a logger for this module
logger = logging.getLogger(__name__)


class CommonSetup(base_CommonSetup):
    # unwanted keys to delete from config
    keys_regex_to_delete_from_config = ( r'\S{3} \S{3} \d{1,2} \d{1,2}:\d{1,2}:\d{1,2}\.\d{1,3} \S{3}',
                                         r'\!\!\d{1,2}:\d{1,2}:\d{1,2} \S{3} \S{3} \S{3} \d{1,2} \d{4,}'
                                        )

    @aetest.subsection
    def learn_configs(self, testbed, steps, report_directory):
        """Learn and save configurations on the testbed devices."""

        # Types of configs to learn
        config_types = { "config_running": "show running-config",
                    "config_failed": "show configuration failed",
                    "config_failed_startup": "show configuration failed startup"
                    }

        # loop over every device in testbed
        for device_name, device in testbed.devices.items():

            # create new steps context for each device
            info_message = f"Learning Configs for {device_name}."
            with steps.start(info_message, continue_=True) as device_step:
                logger.info(info_message)

                # loop over every config type
                for config_type in config_types:

                    # output file name and path
                    output_file_name = f"{device_name}_{config_type}.json"
                    output_file_path = os.path.join(report_directory, output_file_name)

                    # create new steps context for each config type
                    info_message =f"Learning config_type: {config_type}  for device: {device_name}"
                    with device_step.start(info_message, continue_=True) as config_type_step:
                        logger.info(info_message)

                        # skipp the task if the output files already exist
                        if os.path.exists(output_file_path) and os.path.isfile(output_file_path):
                            device_step.skipped(f"Output file: {output_file_path} already exist.")

                        # fail the task if device is not connected
                        elif not device.connected():
                            device_step.failed(f"Device {device_name} is not connected.")

                        else:
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
                                with open(output_file_path, "w") as f:
                                    json.dump(config_tree.config, f ,sort_keys=True, indent=4)
                            except BaseException as e:
                                config_type_step.failed(f"Coudn't learn config_type: {config_type}  for device: {device_name}, reason: {e}.")
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
    def setup(self, testbed, steps, pre, post, report_directory):
        """Read the learned configurations from json file for every the testbed devices."""

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
                f"Reading pre saved configs from {device_name}", continue_=True
            ) as device_step:

                # loop over every config type
                for config_type in self.config_types:
                    with device_step.start(
                        f"Reading config_type: {config_type}, from device: {device_name}", continue_=True
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


class CommonCleanup(base_CommonCleanup):
    pass


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
    parser.add_argument(
        "--offline",
        dest="offline",
        help="offline mode",
        type=bool,
        # type=Genie.init,
        default=None,
    )

    # do the parsing
    args, sys.argv[1:] = parser.parse_known_args(sys.argv[1:])

    aetest.main(testbed=args.testbed, pre=args.pre, post=args.post, offline=args.offline)