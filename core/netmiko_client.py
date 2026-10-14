"""Netmiko SSH connector and automatic login handler for Huawei, Cisco, and Juniper devices."""

import time
import re
from typing import Dict, Any, Tuple, Optional
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
    SSHException
)
from core.commands import get_vendor_command, get_netmiko_device_type
from core.bgp_parser import parse_bgp_summary, parse_bgp_routes

DEFAULT_TIMEOUT = 30

def build_netmiko_device_params(device: Dict[str, Any], timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Construct Netmiko device parameters from inventory dictionary."""
    vendor = device.get("vendor", "cisco_ios")
    device_type = get_netmiko_device_type(vendor)

    params = {
        "device_type": device_type,
        "host": device.get("host", ""),
        "port": int(device.get("port", 22)),
        "username": device.get("username", ""),
        "password": device.get("password", ""),
        "timeout": timeout,
        "conn_timeout": timeout,
        "auth_timeout": timeout,
        "banner_timeout": timeout,
        "fast_cli": False,
        "session_log": None
    }

    if device.get("secret"):
        params["secret"] = device.get("secret")

    if device.get("ssh_key_file"):
        params["use_keys"] = True
        params["key_file"] = device.get("ssh_key_file")

    return params

def test_device_connection(device: Dict[str, Any], timeout: int = 8) -> Tuple[bool, str, float]:
    """
    Test SSH connection and automatic login.
    Returns: (success: bool, message: str, elapsed_ms: float)
    """
    start_time = time.time()
    params = build_netmiko_device_params(device, timeout=timeout)
    
    try:
        connection = ConnectHandler(**params)
        prompt = connection.find_prompt()
        
        # If Cisco and secret provided, enter enable mode
        if "cisco" in device.get("vendor", "").lower() and device.get("secret"):
            if not connection.check_enable_mode():
                connection.enable()
                prompt = connection.find_prompt()

        connection.disconnect()
        elapsed = round((time.time() - start_time) * 1000, 2)
        return True, f"Connected successfully. Prompt: {prompt}", elapsed
    except NetmikoAuthenticationException as e:
        elapsed = round((time.time() - start_time) * 1000, 2)
        return False, f"Authentication Failed: Check username or password ({e})", elapsed
    except NetmikoTimeoutException as e:
        elapsed = round((time.time() - start_time) * 1000, 2)
        return False, f"Connection Timeout: Device {device.get('host')} unreachable on port {device.get('port', 22)}", elapsed
    except SSHException as e:
        elapsed = round((time.time() - start_time) * 1000, 2)
        return False, f"SSH Protocol Error: {e}", elapsed
    except Exception as e:
        elapsed = round((time.time() - start_time) * 1000, 2)
        return False, f"Connection Error: {str(e)}", elapsed

def execute_device_command(device: Dict[str, Any], command: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, str]:
    """
    Connect, run a command, and return (success, raw_output).
    Includes automatic pagination handling and vendor pipe optimizations (| no-more).
    """
    params = build_netmiko_device_params(device, timeout=timeout)
    vendor = str(device.get("vendor", "cisco_ios")).lower()
    clean_cmd = command.strip()

    # Huawei VRP: Ensure '| no-more' is appended to display commands if not already present
    if "huawei" in vendor and clean_cmd.startswith("display") and "|" not in clean_cmd:
        clean_cmd = f"{clean_cmd} | no-more"
    # Juniper Junos: Ensure '| no-more' is appended to show commands if not already present
    elif ("juniper" in vendor or "junos" in vendor) and clean_cmd.startswith("show") and "|" not in clean_cmd:
        clean_cmd = f"{clean_cmd} | no-more"

    try:
        connection = ConnectHandler(**params)
        
        if "cisco" in vendor and device.get("secret"):
            if not connection.check_enable_mode():
                connection.enable()

        prompt = connection.find_prompt()
        more_pattern = r"(---- More ----|---\(more.*?\)|---\(more\)---)"

        try:
            output = connection.send_command(
                clean_cmd,
                read_timeout=timeout,
                expect_string=rf"({re.escape(prompt)}|{more_pattern})"
            )
        except Exception:
            # Fallback to timing if regex expect_string has issues
            output = connection.send_command_timing(clean_cmd, read_timeout=timeout)

        # Handle pagination prompts if router still paused at -- More --
        loops = 0
        while loops < 150 and re.search(more_pattern, output[-250:] if len(output) > 250 else output):
            loops += 1
            try:
                chunk = connection.send_command(
                    " ",
                    read_timeout=timeout,
                    expect_string=rf"({re.escape(prompt)}|{more_pattern})"
                )
                output += chunk
                if prompt in chunk:
                    break
            except Exception:
                break

        # Clean leftover pager banners from final output
        output = re.sub(r"\s*---- More ----\s*", "\n", output)
        output = re.sub(r"\s*---\(more.*?\)---\s*", "\n", output)

        connection.disconnect()
        return True, output.strip()
    except NetmikoAuthenticationException:
        return False, f"Authentication failed for {device.get('name')} ({device.get('host')})"
    except NetmikoTimeoutException:
        return False, f"Timeout connecting to {device.get('name')} ({device.get('host')})"
    except Exception as e:
        return False, f"Command execution failed on {device.get('name')}: {str(e)}"

def get_live_bgp_summary(device: Dict[str, Any], timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, str, list]:
    """Retrieve BGP summary via Netmiko and parse output."""
    vendor = device.get("vendor", "cisco_ios")
    cmd = get_vendor_command(vendor, "summary")
    success, output = execute_device_command(device, cmd, timeout=timeout)
    if not success:
        return False, output, []
    parsed_peers = parse_bgp_summary(vendor, output)
    return True, output, parsed_peers

def get_live_neighbor_routes(device: Dict[str, Any], neighbor_ip: str, route_type: str = "received", timeout: int = 45) -> Tuple[bool, str, list]:
    """Retrieve advertised or received routes for a neighbor via Netmiko."""
    vendor = device.get("vendor", "cisco_ios")
    cmd_type = "advertised_routes" if route_type == "advertised" else "received_routes"
    cmd = get_vendor_command(vendor, cmd_type, peer_ip=neighbor_ip)
    success, output = execute_device_command(device, cmd, timeout=timeout)
    if not success:
        return False, output, []
    parsed_routes = parse_bgp_routes(vendor, output)
    return True, output, parsed_routes
