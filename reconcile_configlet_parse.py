import argparse
import re
import sys
from cvprac.cvp_client import CvpClient
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def parseargs():
    parser = argparse.ArgumentParser(
        description="CVP reconcile configlet parsing for device")
    parser.add_argument("--cvp", dest="cvp", required=True,
                        action="store", help="IP Address of CVP")
    parser.add_argument("--user", dest="user", required=True,
                        action="store", help="User for CVP")
    parser.add_argument("--passw", dest="passw", required=True,
                        action="store", help="Password for CVP")
    parser.add_argument("--device", dest="device", required=True,
                        action="store",
                        help="FQDN of device to parse reconcile configlet")
    args = parser.parse_args()
    return args


def parse_reconcile_config(config):
    config_lines = config.split("\n")
    port_configs_dict = dict()
    reconcile_configs_list = []
    current_int = None
    for line in config_lines:
        if (line.startswith("interface Ethernet") or
                line.startswith("interface Port-Channel")):
            port_configs_dict[line] = []
            current_int = line
        elif line.startswith("   ") and current_int is not None:
            port_configs_dict[current_int].append(line)
        else:
            current_int = None
            reconcile_configs_list.append(line)
    for port, config in port_configs_dict:
        if re.match(r"interface Ethernet[1-8]/\d+/[2-4]", port):
            port_configs_dict.pop(port, None)
    return port_configs_dict, reconcile_configs_list

def configlet_upload(cvp_client, device, configlet_dict):
    # Sort ports based on config type
    new_tap_dict = {}
    new_tool_dict = {}
    new_shut_dict = {}
    for port in configlet_dict:
        for config_line in configlet_dict[port]:
            if "tap" in config_line:
                new_tap_dict[port] = configlet_dict[port]
            elif "tool" in config_line:
                new_tool_dict[port] = configlet_dict[port]
            elif "shutdown" in config_line:
                if "   switchport mode tap" in configlet_dict[port]:
                    continue
                elif "   switchport mode tool" in configlet_dict[port]:
                    continue
                else:
                    new_shut_dict[port] = configlet_dict[port]
    if new_tap_dict:
        print "UPDATING TAP PORTS AUTOMATION CONFIGLET"
        old_tap_configlet = cvp_client.api.get_configlet_by_name(device + "-tapports-automation")
        final_tap_configlet = ""
        for port in new_tap_dict:
            final_tap_configlet+=str("!\n" + port + "\n")
            for port_setting in new_tap_dict[port]:
                final_tap_configlet+=str(port_setting + "\n")
            if "   shutdown" not in new_tap_dict[port]:
                final_tap_configlet+=str("   no shutdown\n")
        final_tap_configlet+=str("!\n")
        resp = cvp_client.api.update_configlet(
            final_tap_configlet, old_tap_configlet["key"], old_tap_configlet["name"], wait_task_ids=False
        )
        if resp is None:
            print "Failed to get update Tap Ports configlet. Exiting"
            sys.exit(1)
    if new_tool_dict:
        print "UPDATING TOOL PORTS AUTOMATION CONFIGLET"
        old_tool_configlet = cvp_client.api.get_configlet_by_name(device + "-toolports-automation")
        final_tool_configlet = ""
        for port in new_tool_dict:
            final_tool_configlet+=str("!\n" + port + "\n")
            for port_setting in new_tool_dict[port]:
                final_tool_configlet+=str(port_setting + "\n")
            if "   shutdown" not in new_tool_dict[port]:
                final_tool_configlet+=str("   no shutdown\n")
        final_tool_configlet+=str("!\n")
        resp = cvp_client.api.update_configlet(
            final_tool_configlet, old_tool_configlet["key"], old_tool_configlet["name"], wait_task_ids=False
        )
        if resp is None:
            print "Failed to get update Tool Ports configlet. Exiting"
            sys.exit(1)
    if new_shut_dict:
        print "UPDATING SHUTDOWN PORTS AUTOMATION CONFIGLET"
        old_shut_configlet = cvp_client.api.get_configlet_by_name(device + "-shutdownports-automation")
        final_shut_configlet = ""
        for port in new_shut_dict:
            final_shut_configlet+=str("!\n" + port + "\n   shutdown\n")
        final_shut_configlet+=str("!\n")
        resp = cvp_client.api.update_configlet(
            final_shut_configlet, old_shut_configlet["key"], old_shut_configlet["name"], wait_task_ids=False
        )
        if resp is None:
            print "Failed to get update Shutdown Ports configlet. Exiting"
            sys.exit(1)

def main():
    options = parseargs()
    # Make connection to CVP
    client = CvpClient()
    client.connect([options.cvp], options.user, options.passw)
    resp = client.api.get_cvp_info()
    if resp is None:
        print "Failed to get CVP info. Exiting"
        sys.exit(1)

    dev_info = client.api.get_device_by_name(options.device)
    if dev_info is None:
        print "Unable to find device %s. Exiting" % options.device
        sys.exit(1)
    print "FOUND DEVICE INFO"

    dev_configlets = client.api.get_configlets_by_device_id(
        dev_info["systemMacAddress"])
    if dev_configlets is None:
        print "Found no configlets for device %s. Exiting" % options.device
        sys.exit(1)
    print "FOUND DEVICE CONFIGLETS"
    reconcile_configlet = None
    for configlet in dev_configlets:
        if "reconciled" in configlet and configlet["reconciled"] is True:
            reconcile_configlet = configlet

    if reconcile_configlet is None:
        print "No reconcile configlet for device %s. Exiting" % options.device
        sys.exit(1)
    print "FOUND DEVICE RECONCILE CONFIGLET"
    # Call function to parse interfaces and non-interfaces from Recocile Configlet
    automation_configlet_dict, reconcile_configlet_list = parse_reconcile_config(reconcile_configlet["config"])
    # Call function to update automation configlets with necessary ports
    configlet_upload(client, options.device, automation_configlet_dict)
    # Update Reconcile Configlet to remove interfaces moved to automation
    print "UPDATING RECONCILE CONFIGLET TO REMOVE INTERFACES"
    reconcile_config = ""
    for line in reconcile_configlet_list:
        reconcile_config+=str(line + "\n")
    data = {
        "name": reconcile_configlet["name"],
        "config": reconcile_config,
        "key": reconcile_configlet["key"],
        "reconciled": True
    }
    resp = client.post("/provisioning/updateReconcileConfiglet.do?netElementId=" + dev_info["systemMacAddress"], data=data)

if __name__ == "__main__":
    main()
