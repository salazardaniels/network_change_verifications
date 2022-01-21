"""
interface_verifications.py
Verify that no errors have been reported on network interfaces in the testbed.
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
    def learn_interface(self, testbed, pre, post):
        """Learn and save the interface details from the testbed devices."""
        # skipp the task if the report_directory_alredy_exist
        if self.report_directory_alredy_exist:
            self.skipped("Don't need to near interface feature if the report_directory_alredy_exist ")

        # set the report_directory, either pre or post
        if pre and post:
            report_directory = post
        elif pre:
            report_directory = pre

        # crerate a dic to store interface information per device
        learnt_interfaces = {}
        for device_name, device in testbed.devices.items():

            # Only attempt to learn details on supported network operation systems
            if device.os in ("ios", "iosxe", "iosxr", "nxos"):
                logger.info(f"{device_name} connected status: {device.connected}")
                logger.info(f"Learning Interfaces for {device_name}")
                learnt_interfaces[device_name] = device.learn("interface").info
                with open(os.path.join(report_directory, f"{device_name}_interface.json"), "w") as f:
                    json.dump(learnt_interfaces[device_name], f ,sort_keys=True, indent=4)


class interface_errors(aetest.Testcase):
    """interface_errors
    < docstring description of this testcase >
    """

    # List of counters keys to check for errors
    #   Model details: https://pubhub.devnetcloud.com/media/genie-feature-browser/docs/_models/interface.pdf
    counter_error_keys = ("in_crc_errors", "in_errors", "out_errors", "in_discards", "out_discard", "in_unknown_protos")
    
    @aetest.setup
    def setup(self, testbed, pre, post):
        """Read the learned interface details from json file for every the testbed devices."""
        # dicts to store device interface information
        self.learnt_interfaces = {}
        self.pre_learnt_interfaces = {} if post else None
        # loop over every device to learn its interfaces
        for device_name, device in testbed.devices.items():
            # Trye to read pre learned interface information
            try:
                with open(os.path.join(post if (pre and post) else pre, f"{device_name}_interface.json"), "r") as f:
                    self.learnt_interfaces[device_name] = json.loads(f.read())
                if post:
                    with open(os.path.join(pre, f"{device_name}_interface.json"), "r") as f:
                        self.pre_learnt_interfaces[device_name] = json.loads(f.read())
            except:
                self.failed(f"Unable to read interface information for device {device_name} from json file")

    @aetest.test
    def interface_errors(self, steps, post):
        # Loop over every device with learnt interfaces
        for device_name, interfaces in self.learnt_interfaces.items():
            with steps.start(
                f"Looking for Interface Errors on {device_name}", continue_=True
            ) as device_step:

                # Loop over every interface that was learnt
                for interface_name, interface in interfaces.items():
                    with device_step.start(
                        f"Checking Interface {interface_name}", continue_=True
                    ) as interface_step:
                        # Create a dict to store the failed counters 
                        failed_counters = { 'pre': {},
                                            'post':{},
                                            }
                        # Verify that this interface has 'counters' (Loopbacks Lack Counters on some platforms)
                        if 'counters' in interface.keys():
                            # Demonstration: Updating a test to log more details
                            #   Uncomment the below logger.info line to write to the log the contents of the 'counters' key
                            logger.info(f"Device {device_name}, Interface {interface_name}, counters: {interface['counters']}")

                            # Loop over every counter to check, looking for values greater than 0
                            for counter in self.counter_error_keys:
                                # Verify that the counter is available for this device
                                if counter in interface['counters'].keys():
                                    if interface['counters'][counter] > 0:
                                        # if in post stage, compare with pre stage
                                        if post:
                                            try:
                                                if interface['counters'][counter] != self.pre_learnt_interfaces[device_name][interface_name]['counters'][counter]:
                                                    failed_counters['post'][counter] = interface['counters'][counter]
                                            except KeyError:
                                                interface_step.failed(
                                                    f'No pre learnt information for {device_name}, Interface {interface_name}, counter {counter}'
                                                )
                                        else:
                                            failed_counters['pre'][counter] = interface['counters'][counter]
                                else:
                                    # if the counter not supported, log that it wasn't checked
                                    logger.info(
                                        f"Device {device_name} Interface {interface_name} missing {counter}"
                                    )
                            # Verify failed_counters exist and mark the interface step as failed if so
                            if failed_counters['post'] :
                                failed_message = ""
                                for failed_counter in failed_counters['post']:
                                    failed_message += f"Device: {device_name}, Interface: {interface_name}, counter: {failed_counter}, has a difference off {interface['counters'][failed_counter]-self.pre_learnt_interfaces[device_name][interface_name]['counters'][failed_counter]} between pre and post verifications. Pre: {self.pre_learnt_interfaces[device_name][interface_name]['counters'][failed_counter]}, Post: {interface['counters'][failed_counter]}\n"
                                #
                                interface_step.failed(failed_message)
                            elif failed_counters['pre']:
                                #
                                interface_step.failed(
                                    f"Device {device_name}, Interface {interface_name}, has a count of {tuple(failed_counters['pre'].values())} for {tuple(failed_counters['pre'].keys())} counter{'s' if len(failed_counters['pre']) > 1 else ''}"
                                )
                            else:
                                interface_step.passed(f'Device {device_name} Interface {interface_name} has no count for {self.counter_error_keys} error counters')
                        else:
                            # If the interface has no counters, mark as skipped
                            interface_step.skipped(
                                f"Device {device_name} Interface {interface_name} missing counters"
                            )


class interface_or_traffic_down(aetest.Testcase):
    """interface_or_traffic_down
    < docstring description of this testcase >
    """

    # List of counters keys to check for traffic rate
    #   Model details: https://pubhub.devnetcloud.com/media/genie-feature-browser/docs/_models/interface.pdf
    rate_counters_keys = ("in_rate_pkts", "out_rate_pkts")

    # List of down oper_status
    #   Model details: https://pubhub.devnetcloud.com/media/genie-feature-browser/docs/_models/interface.pdf
    down_oper_status_values = ("down")
    
    @aetest.setup
    def setup(self, testbed, pre, post):
        """Read the learned interface details from json file for every the testbed devices."""
        # dicts to store device interface information
        self.learnt_interfaces = {}
        self.pre_learnt_interfaces = {} if post else None
        # loop over every device to learn its interfaces
        for device_name, device in testbed.devices.items():
            # Trye to read pre learned interface information
            try:
                with open(os.path.join(post if (pre and post) else pre, f"{device_name}_interface.json"), "r") as f:
                    self.learnt_interfaces[device_name] = json.loads(f.read())
                if post:
                    with open(os.path.join(pre, f"{device_name}_interface.json"), "r") as f:
                        self.pre_learnt_interfaces[device_name] = json.loads(f.read())
            except:
                self.failed(f"Unable to read interface information for device {device_name} from json file")

    @aetest.test
    def interface_or_traffic_down(self, steps, post):
        # Loop over every device with learnt interfaces
        for device_name, interfaces in self.learnt_interfaces.items():
            with steps.start(
                f"Looking for Interfaces down or Traffic down {device_name}", continue_=True
            ) as device_step:
                # Loop over every interface that was learnt
                for interface_name, interface in interfaces.items():
                    with device_step.start(
                        f"Checking Interface {interface_name}", continue_=True
                    ) as interface_step:
                        # Verify that this interfaces has "oper_status" down
                        if 'oper_status' in interface.keys():
                            if interface['oper_status'] in self.down_oper_status_values:
                                if post:
                                    try:
                                        if interface['oper_status'] != self.pre_learnt_interfaces[device_name][interface_name]['oper_status']:
                                            interface_step.failed(
                                                f"Device {device_name}, Interface {interface_name}, Pre and Post oper_status are different. Pre: {self.pre_learnt_interfaces[device_name][interface_name]['oper_status']}, Post: {interface['oper_status']}"
                                            )
                                    except KeyError:
                                        interface_step.failed(
                                            f'No pre learnt information for {device_name}, Interface {interface_name}, oper_status'
                                        )
                                else:
                                    # if interface is enabled/no-shut and down, mark as failed
                                    if interface['enabled']:
                                        interface_step.failed(
                                            f'Device {device_name}, Interface {interface_name} is down'
                                        )
                                    else:
                                        # If the interface is in admin-down/shut, mark as skipped
                                        interface_step.skipped(
                                            f"Device {device_name} Interface {interface_name} is in admin-down"
                                        )
                            else:
                                pass
                        else:
                            pass

                        # Verify that this interface has "counters" (Loopbacks Lack Counters on some platforms)
                        if 'counters' in interface.keys():
                            # Verify that this interface has "rate"
                            if "rate" in interface['counters'].keys():
                                # Demonstration: Updating a test to log more details
                                #   Uncomment the below logger.info line to write to the log the contents of the 'counters' key
                                logger.info(f"Device {device_name}, Interface {interface_name}, rate counters: {interface['counters']['rate']}")
                               
                                # Create a dict to store the failed rate counters 
                                failed_rate_counters = { 'pre': {},
                                                         'post': {},
                                                        }
                               
                                # Loop over every rate counter to check, looking for values equal to 0
                                for rate_counter in self.rate_counters_keys:
                                    # Verify that the counter is available for this device
                                    if rate_counter in interface['counters']['rate'].keys():
                                        # Check if any rate counter is 0
                                        if interface['counters']['rate'][rate_counter] == 0:
                                            # if in post stage, compare with pre stage
                                            if post:
                                                try:
                                                    if interface['counters']['rate'][rate_counter] != self.pre_learnt_interfaces[device_name][interface_name]['counters']['rate'][rate_counter]:
                                                        failed_rate_counters['post'][counter] = interface['counters'][counter]
                                                except KeyError:
                                                    interface_step.failed(
                                                        f'No pre learnt information for {device_name}, Interface {interface_name}, rate counter {rate_counter}'
                                                    )
                                            else:
                                                failed_rate_counters['pre'][rate_counter] = interface['counters']['rate'][rate_counter]
                                    else:
                                        # if the counter not supported, log that it wasn't checked
                                        logger.info(
                                            f"Device {device_name} Interface {interface_name} missing {rate_counter}"
                                        )
                                # Verify failed_rate_counters exist and mark the interface step as failed if so
                                if failed_rate_counters['post']:
                                    failed_message = ""
                                    for failed_rate_counter in failed_rate_counters['post']:
                                        failed_message += f"Device: {device_name}, Interface: {interface_name}, counter: {failed_rate_counter}, has a difference off {interface['counters'][failed_rate_counter]-self.pre_learnt_interfaces[device_name][interface_name]['counters'][failed_rate_counter]} between pre and post verifications. Pre: {self.pre_learnt_interfaces[device_name][interface_name]['counters'][failed_rate_counter]}, Post: {interface['counters'][failed_rate_counter]}\n"
                                    #
                                    interface_step.failed(failed_message)
                                elif failed_rate_counters['pre']:
                                    #
                                    interface_step.failed(
                                        f"Device {device_name}, Interface {interface_name}, has a count of {tuple(failed_rate_counters['pre'].values())} for {tuple(failed_rate_counters['pre'].keys())} counter{'s' if len(failed_rate_counters['pre']) > 1 else ''}"
                                    )
                                else:
                                    interface_step.passed(f'Device {device_name} Interface {interface_name} has traffic counters')

    @aetest.test
    def interface_in_half_duplex(self, steps, post):
        # Loop over every device with learnt interfaces
        for device_name, interfaces in self.learnt_interfaces.items():
            with steps.start(
                f"Looking for Interfaces in half-duplex {device_name}", continue_=True
            ) as device_step:
                # Loop over every interface that was learnt
                for interface_name, interface in interfaces.items():
                    with device_step.start(
                        f"Checking Interface {interface_name}", continue_=True
                    ) as interface_step:
                        # Verify that this interfaces has "duplex_mode" down
                        if 'duplex_mode' in interface.keys():
                            if interface['duplex_mode'] == 'half':
                                if post:
                                    try:
                                        if interface['duplex_mode'] != self.pre_learnt_interfaces[device_name][interface_name]['duplex_mode']:
                                            interface_step.failed(
                                                f"Device {device_name}, Interface {interface_name}, Pre and Post duplex_mode are different. Pre: {self.pre_learnt_interfaces[device_name][interface_name]['duplex_mode']}, Post: {interface['duplex_mode']}"
                                            )
                                    except KeyError:
                                        interface_step.failed(
                                            f'No pre learnt information for {device_name}, Interface {interface_name}, about duplex_mode'
                                        )
                                else:
                                    # if interface is enabled/no-shut and down, mark as failed
                                    if interface['enabled'] :
                                        interface_step.failed(
                                            f'Device {device_name}, Interface {interface_name}, is in half-duplex duplex_mode.'
                                        )
                                    else:
                                        # If the interface is in admin-down/shut, mark as skipped
                                        interface_step.skipped(
                                            f"Device {device_name} Interface {interface_name} is admin-down"
                                        )
                            else:
                                pass
                        else:
                            pass


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