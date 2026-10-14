"""BGP command templates and helpers for Huawei, Cisco, and Juniper devices."""

VENDOR_COMMANDS = {
    "cisco_ios": {
        "summary": "show ip bgp summary",
        "peer_detail": "show ip bgp neighbors {peer_ip}",
        "advertised_routes": "show ip bgp neighbors {peer_ip} advertised-routes",
        "received_routes": "show ip bgp neighbors {peer_ip} routes",
        "prefix_lookup": "show ip bgp {prefix}",
        "all_routes": "show ip bgp",
        "netmiko_device_type": "cisco_ios"
    },
    "cisco_xr": {
        "summary": "show bgp summary",
        "peer_detail": "show bgp neighbors {peer_ip}",
        "advertised_routes": "show bgp neighbors {peer_ip} advertised-routes",
        "received_routes": "show bgp neighbors {peer_ip} routes",
        "prefix_lookup": "show bgp {prefix}",
        "all_routes": "show bgp",
        "netmiko_device_type": "cisco_xr"
    },
    "huawei": {
        "summary": "display bgp peer | no-more",
        "peer_detail": "display bgp peer {peer_ip} verbose | no-more",
        "advertised_routes": "display bgp routing-table peer {peer_ip} advertised-routes | no-more",
        "received_routes": "display bgp routing-table peer {peer_ip} received-routes | no-more",
        "prefix_lookup": "display bgp routing-table {prefix} | no-more",
        "all_routes": "display bgp routing-table | no-more",
        "netmiko_device_type": "huawei"
    },
    "juniper_junos": {
        "summary": "show bgp summary | no-more",
        "peer_detail": "show bgp neighbor {peer_ip} | no-more",
        "advertised_routes": "show route advertising-protocol bgp {peer_ip} | no-more",
        "received_routes": "show route receive-protocol bgp {peer_ip} | no-more",
        "prefix_lookup": "show route {prefix} protocol bgp | no-more",
        "all_routes": "show route protocol bgp | no-more",
        "netmiko_device_type": "juniper_junos"
    }
}

def get_vendor_command(vendor: str, command_type: str, **kwargs) -> str:
    """Retrieve command string for vendor with keyword formatting."""
    vendor_key = vendor.lower()
    if "cisco" in vendor_key and "xr" in vendor_key:
        vendor_key = "cisco_xr"
    elif "cisco" in vendor_key:
        vendor_key = "cisco_ios"
    elif "huawei" in vendor_key:
        vendor_key = "huawei"
    elif "juniper" in vendor_key or "junos" in vendor_key:
        vendor_key = "juniper_junos"
    else:
        vendor_key = "cisco_ios"

    cmd_template = VENDOR_COMMANDS.get(vendor_key, {}).get(command_type, "")
    if cmd_template and kwargs:
        try:
            return cmd_template.format(**kwargs)
        except Exception:
            return cmd_template
    return cmd_template

def get_netmiko_device_type(vendor: str) -> str:
    vendor_key = vendor.lower()
    if "cisco" in vendor_key and "xr" in vendor_key:
        return "cisco_xr"
    elif "cisco" in vendor_key:
        return "cisco_ios"
    elif "huawei" in vendor_key:
        return "huawei"
    elif "juniper" in vendor_key or "junos" in vendor_key:
        return "juniper_junos"
    return "cisco_ios"
