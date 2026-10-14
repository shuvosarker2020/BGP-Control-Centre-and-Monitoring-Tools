"""High-fidelity multi-vendor BGP simulator for Huawei, Cisco, and Juniper routers."""

from typing import Dict, List, Any

MOCK_BGP_SUMMARY = {
    "cisco-edge-01": """
BGP router identifier 10.10.10.1, local AS number 65001
BGP table version is 10842, main routing table version 10842
18 network entries using 4464 bytes of memory
36 path entries using 4608 bytes of memory
BGP activity 18/0 prefixes, 36/0 paths, scan interval 60 secs

Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
198.51.100.1    4         3356  124802  124800    10842    0    0 14w2d           945200
198.51.100.5    4         1299   84902   84900    10842    0    0 03w5d           938100
198.51.100.9    4        13335   24100   24100    10842    0    0 01d04h            1450
""",

    "juniper-mx-01": """
Groups: 3 Peers: 3 Down peers: 0
Table          Tot Paths  Act Paths Suppressed    History Damp State    Pending
inet.0            954120     520110          0          0          0          0
Peer                     AS      InPkt     OutPkt    OutQ   Flaps Last Up/Dwn State|#Active/Received/Accepted/Damped...
203.0.113.1            2914     482910     482900       0       0     28w3d 520110/954120/954120/0 0/0/0/0
203.0.113.5            6453     194020     194000       0       1      4w1d 420000/940200/940200/0 0/0/0/0
203.0.113.9           16509      34200      34150       0       0      5d08h 120/120/120/0 0/0/0/0
""",

    "huawei-ne40-01": """
BGP router identifier 10.10.10.3, local AS number 65001
BGP table version is 3582
Total number of peers : 3                 Peers in established state : 3

  Peer            V    AS  MsgRcvd  MsgSent  OutQ  Up/Down       State  PrefRcv
  192.0.2.1       4  6939   154200   154180     0 08w2d    Established   962000
  192.0.2.5       4   174    89200    89150     0 02w1d    Established   948500
  192.0.2.9       4 65002     1250     1250     0 00:32:10 Established       45
"""
}

# Detailed route tables per neighbor for Received and Advertised routes
MOCK_NEIGHBOR_ROUTES: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "198.51.100.1": {  # Cisco -> Lumen
        "received": [
            {"prefix": "1.0.0.0/24", "next_hop": "198.51.100.1", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "3356 13335", "origin": "i", "best": True, "valid": True},
            {"prefix": "8.8.8.0/24", "next_hop": "198.51.100.1", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "3356 15169", "origin": "i", "best": True, "valid": True},
            {"prefix": "1.1.1.0/24", "next_hop": "198.51.100.1", "metric": "10", "loc_pref": "100", "weight": "0", "as_path": "3356 13335", "origin": "i", "best": True, "valid": True},
            {"prefix": "93.184.216.0/24", "next_hop": "198.51.100.1", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "3356 15133", "origin": "i", "best": True, "valid": True},
            {"prefix": "104.16.0.0/12", "next_hop": "198.51.100.1", "metric": "20", "loc_pref": "100", "weight": "0", "as_path": "3356 13335", "origin": "i", "best": True, "valid": True},
            {"prefix": "151.101.0.0/16", "next_hop": "198.51.100.1", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "3356 54113", "origin": "i", "best": True, "valid": True},
            {"prefix": "142.250.0.0/15", "next_hop": "198.51.100.1", "metric": "5", "loc_pref": "100", "weight": "0", "as_path": "3356 15169", "origin": "i", "best": True, "valid": True},
            {"prefix": "199.232.0.0/16", "next_hop": "198.51.100.1", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "3356 54113", "origin": "i", "best": True, "valid": True},
        ],
        "advertised": [
            {"prefix": "203.0.113.0/24", "next_hop": "198.51.100.2", "metric": "0", "loc_pref": "100", "weight": "32768", "as_path": "65001", "origin": "i", "best": True, "valid": True},
            {"prefix": "198.51.100.0/24", "next_hop": "198.51.100.2", "metric": "0", "loc_pref": "100", "weight": "32768", "as_path": "65001", "origin": "i", "best": True, "valid": True},
            {"prefix": "192.0.2.0/24", "next_hop": "198.51.100.2", "metric": "0", "loc_pref": "100", "weight": "32768", "as_path": "65001", "origin": "i", "best": True, "valid": True},
        ]
    },
    "198.51.100.5": {  # Cisco -> Telia / Arelion
        "received": [
            {"prefix": "1.0.0.0/24", "next_hop": "198.51.100.5", "metric": "10", "loc_pref": "100", "weight": "0", "as_path": "1299 13335", "origin": "i", "best": False, "valid": True},
            {"prefix": "8.8.8.0/24", "next_hop": "198.51.100.5", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "1299 15169", "origin": "i", "best": False, "valid": True},
            {"prefix": "1.1.1.0/24", "next_hop": "198.51.100.5", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "1299 13335", "origin": "i", "best": True, "valid": True},
            {"prefix": "13.32.0.0/15", "next_hop": "198.51.100.5", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "1299 16509", "origin": "i", "best": True, "valid": True},
            {"prefix": "52.94.0.0/16", "next_hop": "198.51.100.5", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "1299 16509", "origin": "i", "best": True, "valid": True},
            {"prefix": "17.0.0.0/8", "next_hop": "198.51.100.5", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "1299 714", "origin": "i", "best": True, "valid": True},
        ],
        "advertised": [
            {"prefix": "203.0.113.0/24", "next_hop": "198.51.100.6", "metric": "0", "loc_pref": "100", "weight": "32768", "as_path": "65001", "origin": "i", "best": True, "valid": True},
            {"prefix": "198.51.100.0/24", "next_hop": "198.51.100.6", "metric": "0", "loc_pref": "100", "weight": "32768", "as_path": "65001", "origin": "i", "best": True, "valid": True},
        ]
    },
    "198.51.100.9": {  # Cisco -> Cloudflare
        "received": [
            {"prefix": "1.1.1.0/24", "next_hop": "198.51.100.9", "metric": "0", "loc_pref": "200", "weight": "0", "as_path": "13335", "origin": "i", "best": True, "valid": True},
            {"prefix": "1.0.0.0/24", "next_hop": "198.51.100.9", "metric": "0", "loc_pref": "200", "weight": "0", "as_path": "13335", "origin": "i", "best": True, "valid": True},
            {"prefix": "104.16.0.0/12", "next_hop": "198.51.100.9", "metric": "0", "loc_pref": "200", "weight": "0", "as_path": "13335", "origin": "i", "best": True, "valid": True},
            {"prefix": "172.64.0.0/13", "next_hop": "198.51.100.9", "metric": "0", "loc_pref": "200", "weight": "0", "as_path": "13335", "origin": "i", "best": True, "valid": True},
        ],
        "advertised": [
            {"prefix": "203.0.113.0/24", "next_hop": "198.51.100.10", "metric": "0", "loc_pref": "100", "weight": "32768", "as_path": "65001", "origin": "i", "best": True, "valid": True},
        ]
    },
    "203.0.113.1": {  # Juniper -> NTT
        "received": [
            {"prefix": "1.0.0.0/24", "next_hop": "203.0.113.1", "metric": "0", "loc_pref": "100", "weight": "-", "as_path": "2914 13335", "origin": "I", "best": True, "valid": True},
            {"prefix": "8.8.8.0/24", "next_hop": "203.0.113.1", "metric": "0", "loc_pref": "100", "weight": "-", "as_path": "2914 15169", "origin": "I", "best": True, "valid": True},
            {"prefix": "20.190.128.0/18", "next_hop": "203.0.113.1", "metric": "0", "loc_pref": "100", "weight": "-", "as_path": "2914 8075", "origin": "I", "best": True, "valid": True},
            {"prefix": "40.126.0.0/18", "next_hop": "203.0.113.1", "metric": "0", "loc_pref": "100", "weight": "-", "as_path": "2914 8075", "origin": "I", "best": True, "valid": True},
        ],
        "advertised": [
            {"prefix": "203.0.113.0/24", "next_hop": "203.0.113.2", "metric": "0", "loc_pref": "100", "weight": "-", "as_path": "65001", "origin": "I", "best": True, "valid": True},
        ]
    },
    "203.0.113.5": {  # Juniper -> Tata Communications
        "received": [
            {"prefix": "1.0.0.0/24", "next_hop": "203.0.113.5", "metric": "0", "loc_pref": "100", "weight": "-", "as_path": "6453 13335", "origin": "I", "best": False, "valid": True},
            {"prefix": "8.8.8.0/24", "next_hop": "203.0.113.5", "metric": "5", "loc_pref": "100", "weight": "-", "as_path": "6453 15169", "origin": "I", "best": False, "valid": True},
            {"prefix": "157.240.0.0/16", "next_hop": "203.0.113.5", "metric": "0", "loc_pref": "100", "weight": "-", "as_path": "6453 32934", "origin": "I", "best": True, "valid": True},
            {"prefix": "31.13.64.0/18", "next_hop": "203.0.113.5", "metric": "0", "loc_pref": "100", "weight": "-", "as_path": "6453 32934", "origin": "I", "best": True, "valid": True},
        ],
        "advertised": [
            {"prefix": "203.0.113.0/24", "next_hop": "203.0.113.6", "metric": "0", "loc_pref": "100", "weight": "-", "as_path": "65001", "origin": "I", "best": True, "valid": True},
        ]
    },
    "203.0.113.9": {  # Juniper -> AWS Direct Connect
        "received": [
            {"prefix": "10.50.0.0/16", "next_hop": "203.0.113.9", "metric": "100", "loc_pref": "150", "weight": "-", "as_path": "16509", "origin": "I", "best": True, "valid": True},
            {"prefix": "10.60.0.0/16", "next_hop": "203.0.113.9", "metric": "100", "loc_pref": "150", "weight": "-", "as_path": "16509", "origin": "I", "best": True, "valid": True},
            {"prefix": "172.31.0.0/16", "next_hop": "203.0.113.9", "metric": "100", "loc_pref": "150", "weight": "-", "as_path": "16509", "origin": "I", "best": True, "valid": True},
        ],
        "advertised": [
            {"prefix": "10.100.0.0/16", "next_hop": "203.0.113.10", "metric": "0", "loc_pref": "100", "weight": "-", "as_path": "65001", "origin": "I", "best": True, "valid": True},
        ]
    },
    "192.0.2.1": {  # Huawei -> Hurricane Electric
        "received": [
            {"prefix": "1.0.0.0/24", "next_hop": "192.0.2.1", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "6939 13335", "origin": "i", "best": True, "valid": True},
            {"prefix": "8.8.8.0/24", "next_hop": "192.0.2.1", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "6939 15169", "origin": "i", "best": True, "valid": True},
            {"prefix": "199.16.156.0/22", "next_hop": "192.0.2.1", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "6939 13414", "origin": "i", "best": True, "valid": True},
            {"prefix": "140.82.112.0/20", "next_hop": "192.0.2.1", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "6939 36459", "origin": "i", "best": True, "valid": True},
        ],
        "advertised": [
            {"prefix": "192.0.2.0/24", "next_hop": "192.0.2.2", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "65001", "origin": "i", "best": True, "valid": True},
        ]
    },
    "192.0.2.5": {  # Huawei -> Cogent
        "received": [
            {"prefix": "1.0.0.0/24", "next_hop": "192.0.2.5", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "174 13335", "origin": "i", "best": False, "valid": True},
            {"prefix": "8.8.8.0/24", "next_hop": "192.0.2.5", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "174 15169", "origin": "i", "best": False, "valid": True},
            {"prefix": "199.96.56.0/21", "next_hop": "192.0.2.5", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "174 13414", "origin": "i", "best": True, "valid": True},
        ],
        "advertised": [
            {"prefix": "192.0.2.0/24", "next_hop": "192.0.2.2", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "65001", "origin": "i", "best": True, "valid": True},
        ]
    },
    "192.0.2.9": {  # Huawei -> Regional IXP
        "received": [
            {"prefix": "103.25.100.0/24", "next_hop": "192.0.2.9", "metric": "0", "loc_pref": "300", "weight": "0", "as_path": "65002", "origin": "i", "best": True, "valid": True},
            {"prefix": "103.25.101.0/24", "next_hop": "192.0.2.9", "metric": "0", "loc_pref": "300", "weight": "0", "as_path": "65002", "origin": "i", "best": True, "valid": True},
            {"prefix": "45.112.0.0/22", "next_hop": "192.0.2.9", "metric": "0", "loc_pref": "300", "weight": "0", "as_path": "65002", "origin": "i", "best": True, "valid": True},
        ],
        "advertised": [
            {"prefix": "192.0.2.0/24", "next_hop": "192.0.2.2", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "65001", "origin": "i", "best": True, "valid": True},
            {"prefix": "203.0.113.0/24", "next_hop": "192.0.2.2", "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "65001", "origin": "i", "best": True, "valid": True},
        ]
    }
}

def get_simulated_summary_output(device_id: str, vendor: str) -> str:
    """Return raw BGP summary CLI output for device."""
    if device_id in MOCK_BGP_SUMMARY:
        return MOCK_BGP_SUMMARY[device_id]
    if "juniper" in vendor.lower():
        return MOCK_BGP_SUMMARY["juniper-mx-01"]
    elif "huawei" in vendor.lower():
        return MOCK_BGP_SUMMARY["huawei-ne40-01"]
    return MOCK_BGP_SUMMARY["cisco-edge-01"]

def get_simulated_neighbor_routes(neighbor_ip: str, route_type: str = "received") -> List[Dict[str, Any]]:
    """Return structured routes for a neighbor in simulation mode."""
    if neighbor_ip in MOCK_NEIGHBOR_ROUTES:
        return MOCK_NEIGHBOR_ROUTES[neighbor_ip].get(route_type, [])
    # Default fallback routes
    if route_type == "advertised":
        return [
            {"prefix": "203.0.113.0/24", "next_hop": "Self", "metric": "0", "loc_pref": "100", "weight": "32768", "as_path": "65001", "origin": "i", "best": True, "valid": True}
        ]
    return [
        {"prefix": "1.0.0.0/24", "next_hop": neighbor_ip, "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "65000", "origin": "i", "best": True, "valid": True},
        {"prefix": "8.8.8.0/24", "next_hop": neighbor_ip, "metric": "0", "loc_pref": "100", "weight": "0", "as_path": "65000 15169", "origin": "i", "best": True, "valid": True}
    ]
