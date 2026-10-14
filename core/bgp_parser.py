import re
from typing import List, Dict, Any, Optional

def normalize_peer_state(state_raw: str) -> str:
    """Normalize state representation across vendors."""
    s = state_raw.strip()
    if not s:
        return "Unknown"
    if s.isdigit():
        return "Established"
    sl = s.lower()
    if "estab" in sl:
        return "Established"
    if "idle" in sl:
        return "Idle"
    if "active" in sl:
        return "Active"
    if "open" in sl:
        return "OpenConfirm/OpenSent"
    if "connect" in sl:
        return "Connect"
    return s.capitalize()

def parse_cisco_bgp_summary(output: str) -> List[Dict[str, Any]]:
    """Parse 'show ip bgp summary' or 'show bgp summary'."""
    results = []
    lines = output.splitlines()
    in_neighbor_section = False
    
    # Example line:
    # 198.51.100.1    4         3356  124802  124800    10842    0    0 14w2d           945200
    # 198.51.100.13   4        65005       0       0        0    0    0 never          Active
    pattern = re.compile(
        r"^([0-9a-fA-F:\.]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)"
    )

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        if "Neighbor" in line and "AS" in line and "State" in line:
            in_neighbor_section = True
            continue
        if in_neighbor_section:
            match = pattern.match(line_clean)
            if match:
                neighbor_ip = match.group(1)
                version = match.group(2)
                remote_as = int(match.group(3))
                msg_rcvd = int(match.group(4))
                msg_sent = int(match.group(5))
                uptime = match.group(9)
                state_pfx = match.group(10)
                
                if state_pfx.isdigit():
                    state = "Established"
                    pfx_rcvd = int(state_pfx)
                else:
                    state = normalize_peer_state(state_pfx)
                    pfx_rcvd = 0

                results.append({
                    "neighbor_ip": neighbor_ip,
                    "version": version,
                    "remote_as": remote_as,
                    "msg_rcvd": msg_rcvd,
                    "msg_sent": msg_sent,
                    "uptime": uptime,
                    "state": state,
                    "pfx_rcvd": pfx_rcvd,
                    "raw_state": state_pfx
                })
    return results

def parse_juniper_bgp_summary(output: str) -> List[Dict[str, Any]]:
    """Parse Juniper 'show bgp summary'."""
    results = []
    lines = output.splitlines()
    in_peer_section = False
    
    # Juniper format:
    # Peer                     AS      InPkt     OutPkt    OutQ   Flaps Last Up/Dwn State|#Active/Received/Accepted/Damped...
    # 203.0.113.1            2914     482910     482900       0       0     28w3d 520110/954120/954120/0 0/0/0/0
    # 203.0.113.13          65010          0          0       0       3  00:15:30 Idle
    pattern = re.compile(
        r"^([0-9a-fA-F:\.]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)"
    )

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        if "Peer" in line and "AS" in line and ("State" in line or "Up/Dwn" in line):
            in_peer_section = True
            continue
        if in_peer_section:
            match = pattern.match(line_clean)
            if match:
                peer_ip = match.group(1)
                remote_as = int(match.group(2))
                in_pkt = int(match.group(3))
                out_pkt = int(match.group(4))
                flaps = int(match.group(6))
                uptime = match.group(7)
                state_pfx = match.group(8)

                if "/" in state_pfx:
                    state = "Established"
                    parts = state_pfx.split("/")
                    # Active/Received/Accepted/Damped
                    pfx_rcvd = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                else:
                    state = normalize_peer_state(state_pfx)
                    pfx_rcvd = 0

                results.append({
                    "neighbor_ip": peer_ip,
                    "version": "4",
                    "remote_as": remote_as,
                    "msg_rcvd": in_pkt,
                    "msg_sent": out_pkt,
                    "uptime": uptime,
                    "flaps": flaps,
                    "state": state,
                    "pfx_rcvd": pfx_rcvd,
                    "raw_state": state_pfx
                })
    return results

def parse_huawei_bgp_summary(output: str) -> List[Dict[str, Any]]:
    """Parse Huawei VRP 'display bgp peer'."""
    results = []
    lines = output.splitlines()
    in_peer_section = False
    
    # Huawei format:
    # Peer            V    AS  MsgRcvd  MsgSent  OutQ  Up/Down       State  PrefRcv
    # 192.0.2.1       4  6939   154200   154180     0 08w2d    Established   962000
    # 192.0.2.13      4 65020        0        0     0 00:00:15        Idle        0
    pattern = re.compile(
        r"^([0-9a-fA-F:\.]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s*(\d+)?"
    )

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        if "Peer" in line and "AS" in line and "MsgRcvd" in line:
            in_peer_section = True
            continue
        if in_peer_section:
            match = pattern.match(line_clean)
            if match:
                peer_ip = match.group(1)
                version = match.group(2)
                remote_as = int(match.group(3))
                msg_rcvd = int(match.group(4))
                msg_sent = int(match.group(5))
                uptime = match.group(7)
                state_raw = match.group(8)
                pfx_rcvd_raw = match.group(9)

                state = normalize_peer_state(state_raw)
                pfx_rcvd = int(pfx_rcvd_raw) if pfx_rcvd_raw and pfx_rcvd_raw.isdigit() else 0

                results.append({
                    "neighbor_ip": peer_ip,
                    "version": version,
                    "remote_as": remote_as,
                    "msg_rcvd": msg_rcvd,
                    "msg_sent": msg_sent,
                    "uptime": uptime,
                    "state": state,
                    "pfx_rcvd": pfx_rcvd,
                    "raw_state": state_raw
                })
    return results

def parse_bgp_summary(vendor: str, output: str) -> List[Dict[str, Any]]:
    """Dispatch summary parsing based on vendor."""
    vendor_lower = vendor.lower()
    if "juniper" in vendor_lower:
        return parse_juniper_bgp_summary(output)
    elif "huawei" in vendor_lower:
        return parse_huawei_bgp_summary(output)
    else:
        return parse_cisco_bgp_summary(output)

def parse_bgp_routes(vendor: str, output: str) -> List[Dict[str, Any]]:
    """
    Parse BGP routes (received or advertised) for Cisco, Juniper, and Huawei.
    Returns list of dicts with keys:
    - prefix
    - next_hop
    - metric (MED)
    - loc_pref
    - weight
    - as_path
    - origin
    - best (bool)
    - valid (bool)
    """
    vendor_lower = vendor.lower()
    results = []

    if "juniper" in vendor_lower:
        # Juniper route format:
        # Prefix                  Nexthop              MED     Lclpref AS path
        # * 1.0.0.0/24            203.0.113.1          0       100     2914 13335 I
        #   8.8.8.0/24            203.0.113.1          0       100     2914 15169 I
        for line in output.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("Prefix") or line_str.startswith("inet.") or line_str.startswith("{"):
                continue
            is_best = "*" in line_str[:3]
            clean = line_str.lstrip("*> ").strip()
            parts = clean.split()
            if len(parts) >= 2 and "/" in parts[0]:
                prefix = parts[0]
                next_hop = parts[1]
                med = parts[2] if len(parts) > 2 and parts[2].isdigit() else "-"
                loc_pref = parts[3] if len(parts) > 3 and parts[3].isdigit() else "100"
                as_path_parts = parts[4:] if len(parts) > 4 else []
                origin = as_path_parts[-1] if as_path_parts and as_path_parts[-1] in ["I", "E", "?"] else "I"
                if as_path_parts and as_path_parts[-1] in ["I", "E", "?"]:
                    as_path = " ".join(as_path_parts[:-1])
                else:
                    as_path = " ".join(as_path_parts)
                results.append({
                    "prefix": prefix,
                    "next_hop": next_hop,
                    "metric": med,
                    "loc_pref": loc_pref,
                    "weight": "-",
                    "as_path": as_path if as_path else "Direct",
                    "origin": origin,
                    "best": is_best or True,
                    "valid": True
                })

    elif "huawei" in vendor_lower:
        # Huawei format:
        #   Network          NextHop         MED        LocPrf    PrefVal Path/Ogn
        # *> 1.0.0.0/24      192.0.2.1       0                    0       6939 13335 i
        # *>i 0.0.0.0/0      10.248.42.161
        for line in output.splitlines():
            line_str = line.strip()
            if not line_str or "Network" in line_str or "BGP" in line_str or "Total Number" in line_str or "Status" in line_str or "RPKI" in line_str or "Origin" in line_str:
                continue
            is_best = ">" in line_str[:6]
            is_valid = "*" in line_str[:6] or is_best
            
            parts = line_str.split()
            first_ip_idx = -1
            for i, p in enumerate(parts):
                if ("." in p or ":" in p) and any(c.isdigit() for c in p):
                    first_ip_idx = i
                    break

            if first_ip_idx != -1 and len(parts) > first_ip_idx + 1:
                prefix = parts[first_ip_idx]
                next_hop = parts[first_ip_idx + 1]
                med = "-"
                loc_pref = "-"
                pref_val = "-"
                idx = first_ip_idx + 2

                if idx < len(parts) and parts[idx].isdigit():
                    med = parts[idx]
                    idx += 1
                if idx < len(parts) and parts[idx].isdigit():
                    loc_pref = parts[idx]
                    idx += 1
                if idx < len(parts) and parts[idx].isdigit():
                    pref_val = parts[idx]
                    idx += 1
                as_path_parts = parts[idx:]
                origin = as_path_parts[-1] if as_path_parts and as_path_parts[-1] in ["i", "e", "?"] else "i"
                if as_path_parts and as_path_parts[-1] in ["i", "e", "?"]:
                    as_path = " ".join(as_path_parts[:-1])
                else:
                    as_path = " ".join(as_path_parts)
                results.append({
                    "prefix": prefix,
                    "next_hop": next_hop,
                    "metric": med,
                    "loc_pref": loc_pref if loc_pref != "-" else "100",
                    "weight": pref_val if pref_val != "-" else "0",
                    "as_path": as_path if as_path else "Direct",
                    "origin": origin,
                    "best": is_best,
                    "valid": is_valid
                })

    else:
        # Cisco format:
        #    Network          Next Hop            Metric LocPrf Weight Path
        # *> 1.0.0.0/24       198.51.100.1             0             0 3356 13335 i
        # *  8.8.8.0/24       198.51.100.5             0        100  0 1299 15169 i
        current_prefix = ""
        for line in output.splitlines():
            line_str = line.strip()
            if not line_str or "Network" in line_str or "BGP table" in line_str or "Status codes:" in line_str or "Origin codes:" in line_str:
                continue
            
            is_best = ">" in line[:4]
            is_valid = "*" in line[:4]
            clean = line.lstrip("*> ").strip()
            parts = clean.split()
            
            if not parts:
                continue

            # In Cisco, sometimes prefix is on a line by itself if long
            if len(parts) == 1 and ("." in parts[0] or ":" in parts[0]):
                current_prefix = parts[0]
                continue

            if "/" in parts[0] or (re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", parts[0])):
                current_prefix = parts[0]
                parts = parts[1:]

            if not current_prefix or len(parts) < 1:
                continue

            next_hop = parts[0]
            idx = 1
            med = "-"
            loc_pref = "-"
            weight = "-"
            
            # Cisco fields: Next Hop, Metric, LocPrf, Weight, Path
            if idx < len(parts) and parts[idx].isdigit():
                med = parts[idx]
                idx += 1
            if idx < len(parts) and parts[idx].isdigit():
                loc_pref = parts[idx]
                idx += 1
            if idx < len(parts) and parts[idx].isdigit():
                weight = parts[idx]
                idx += 1

            as_path_parts = parts[idx:]
            origin = as_path_parts[-1] if as_path_parts and as_path_parts[-1] in ["i", "e", "?"] else "i"
            if as_path_parts and as_path_parts[-1] in ["i", "e", "?"]:
                as_path = " ".join(as_path_parts[:-1])
            else:
                as_path = " ".join(as_path_parts)

            results.append({
                "prefix": current_prefix,
                "next_hop": next_hop,
                "metric": med,
                "loc_pref": loc_pref if loc_pref != "-" else "100",
                "weight": weight if weight != "-" else "0",
                "as_path": as_path if as_path else "Direct",
                "origin": origin,
                "best": is_best,
                "valid": is_valid or is_best
            })

    return results
