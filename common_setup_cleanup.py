"""
common_setup_cleanup.py
Common setup and cleanup classes and methods to be imported by other testcases to comply with dry.
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

from pyats import aetest
from genie.testbed import load
from time import sleep
from random import randint

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
            if os.path.exists(pre) and os.path.isdir(pre):
                self.passed(f"Pre verifications Report directory {pre} exists!")
            else:
                self.failed(f"Pre verifications Report directory {pre} does not exists!", goto=['common_cleanup'])

    @aetest.subsection
    def set_common_attributes(self, pre, post, testscript):
        """
        Sets common attributes to be used by several tests.
        """
        # where verification stage is pre or post
        if pre and post:
            testscript.parameters["report_directory"] = post
        elif pre:
            testscript.parameters["report_directory"] = pre

    @aetest.subsection
    def create_report_directory(self, report_directory):
        """
        create report directory
        """
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
            except BaseException as e:
                self.failed(f"Could not create report directory {report_directory}. Reason: {e}")
            self.passed(f"Report directory {report_directory} created successfully")

    @aetest.subsection
    def connect_to_device(self, testbed, steps, offline):
        """
        establishes connection to all your testbed devices.
        """
        if offline:
            self.skipped("Offline mode")

        # make sure testbed is provided
        assert testbed, "Testbed is not provided!"

        # connect to every device if not already connected.
        #   By default ANY error in the CommonSetup will fail the entire test run
        #   Here we catch common exceptions if a device is unavailable to allow test to continue

        for device_name, device in testbed.devices.items():
            # start new step context for each device
            with steps.start(
                f"Connecting to device {device_name}."
            ) as device_step:

                # connnect if device is disconnectd
                if not device.connected:

                    # try to connect to device
                    try:
                        logger.info(
                            f"************************ connected: {device.connected}."
                        )
                        logger.info(
                            f"************************ connecitons: {device.connectionmgr.connections.connections}."
                        )
                        sleep(randint(2,10))
                        device.connect()
                    except:
                        # try 3 more times, waiting a random time between 1 and 10 seconds between each try.
                        for _ in range(3):
                            sleep(randint(2,10))
                            if not device.connected:
                                try:
                                    logger.info(
                                        f"*-*-*-*-*-*-*-*-*-*-*-*-*- connected: {device.connected}."
                                    )
                                    logger.info(
                                        f"*-*-*-*-*-*-*-*-*-*-*-*-*- connecitons: {device.connectionmgr.connections.connections}."
                                    )
                                        # to signal to other proceses that a connection is being handled
                                    device.connect()
                                    break
                                except BaseException as e:
                                    # log and marked the failed step
                                    error_message = f"Unable to connect to device {device_name}. Reason: {e}."
                                    logger.error(error_message)
                                    device_step.skipped(error_message)
                            else:
                                device_step.skipped(f"Device {device_name} is already connected.")
                else:
                    device_step.skipped(f"Device {device_name} is already connected.")

                # log and marked the passed step
                info_message = f"Connection to device {device_name} was stablished successfully."
                logger.info(info_message)
                device_step.passed(info_message)


class CommonCleanup(aetest.CommonCleanup):
    """CommonCleanup Section
    < common cleanup docstring >
    """
    @aetest.subsection
    def disconnect_from_device(self, testbed, steps):
        """
        Disconnects from all your testbed devices if already connected.
        """

        # make sure testbed is provided
        assert testbed, "Testbed is not provided!"

        # disconnect to every device if not already disconnected.
        for device_name, device in testbed.devices.items():
            # start new step context for each device
            with steps.start(
                f"Disconnecting from device {device_name}."
            ) as device_step:

                # skip the step if the device is already disconnected
                if device.connected:

                    # try to disconnect from device 
                    try:
                        # disconnect from all testbed devices
                        logger.info(
                            f"Disconnecting from device {device_name}."
                        )
                    except BaseException as e:
                        # log and marked the failed step
                        error_message = f"Unable to disconnect from device {device_name}. Reason: {e}"
                        logger.error(error_message)
                        device_step.failed(error_message)

                    # log and marked the passed step
                    info_message = f"Successfully disconnected from device {device_name}."
                    logger.info(info_message)
                    device_step.passed(info_message)
                
                else:
                    device_step.skipped(f"Device {device_name} is already disconnected.")


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