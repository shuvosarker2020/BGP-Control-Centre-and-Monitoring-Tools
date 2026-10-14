"""BGP service layer aggregating multi-vendor data, providers, and routes."""

import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from core.device_manager import DeviceManager
from core.database import BGPDatabase
from core.bgp_parser import parse_bgp_summary
from core.simulator import (
    get_simulated_summary_output,
    get_simulated_neighbor_routes,
    MOCK_NEIGHBOR_ROUTES
)
from core.netmiko_client import (
    get_live_bgp_summary,
    get_live_neighbor_routes,
    execute_device_command,
    test_device_connection
)

class BGPService:
    def __init__(self, device_manager: Optional[DeviceManager] = None, database: Optional[BGPDatabase] = None):
        self.dm = device_manager or DeviceManager()
        self.db = database or BGPDatabase()

    def get_devices(self) -> List[Dict[str, Any]]:
        return self.dm.load_devices()

    def get_providers(self) -> List[str]:
        return self.dm.get_all_providers()

    def get_peers(
        self,
        simulation_mode: bool = False,
        device_filter: Optional[List[str]] = None,
        provider_filter: Optional[List[str]] = None,
        status_filter: Optional[str] = "All",
        on_demand_live: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Phase-1 On-Demand BGP Peer Retrieval:
        - When on_demand_live=False: Instantly loads latest peer state from local SQLite database (sub-millisecond).
        - When on_demand_live=True: Performs real-time on-demand SSH query only for requested devices.
        """
        devices = self.get_devices()
        meta_map = self.dm.get_neighbor_meta_map()
        all_peers = []

        if simulation_mode:
            for dev in devices:
                dev_id = dev.get("id")
                dev_name = dev.get("name")
                dev_vendor = dev.get("vendor")
                if device_filter and dev_id not in device_filter and dev_name not in device_filter:
                    continue
                raw_output = get_simulated_summary_output(dev_id, dev_vendor)
                parsed_peers = parse_bgp_summary(dev_vendor, raw_output)
                for p in parsed_peers:
                    ip = p.get("neighbor_ip")
                    meta = meta_map.get(f"{dev_id}:{ip}") or meta_map.get(ip, {})
                    all_peers.append({
                        "device_id": dev_id,
                        "device_name": dev_name,
                        "vendor": dev_vendor,
                        "neighbor_ip": ip,
                        "remote_as": p.get("remote_as"),
                        "provider": meta.get("provider", f"AS{p.get('remote_as')} (Unmapped)"),
                        "description": meta.get("description", ""),
                        "state": p.get("state"),
                        "uptime": p.get("uptime"),
                        "pfx_rcvd": p.get("pfx_rcvd", 0),
                        "msg_rcvd": p.get("msg_rcvd", 0),
                        "msg_sent": p.get("msg_sent", 0)
                    })
        elif on_demand_live:
            # Explicit on-demand live SSH poll
            for dev in devices:
                dev_id = dev.get("id")
                dev_name = dev.get("name")
                dev_vendor = dev.get("vendor")
                if device_filter and dev_id not in device_filter and dev_name not in device_filter:
                    continue

                success, raw_output, parsed = get_live_bgp_summary(dev)
                if success:
                    for p in parsed:
                        ip = p.get("neighbor_ip")
                        meta = meta_map.get(f"{dev_id}:{ip}") or meta_map.get(ip, {})
                        all_peers.append({
                            "device_id": dev_id,
                            "device_name": dev_name,
                            "vendor": dev_vendor,
                            "neighbor_ip": ip,
                            "remote_as": p.get("remote_as"),
                            "provider": meta.get("provider", f"AS{p.get('remote_as')} (Unmapped)"),
                            "description": meta.get("description", ""),
                            "state": p.get("state"),
                            "uptime": p.get("uptime"),
                            "pfx_rcvd": p.get("pfx_rcvd", 0),
                            "msg_rcvd": p.get("msg_rcvd", 0),
                            "msg_sent": p.get("msg_sent", 0)
                        })
                else:
                    all_peers.append({
                        "device_id": dev_id,
                        "device_name": dev_name,
                        "vendor": dev_vendor,
                        "neighbor_ip": "N/A",
                        "remote_as": 0,
                        "provider": "Unreachable Device",
                        "description": f"Failed to login: {raw_output}",
                        "state": "Connection Failed",
                        "uptime": "-",
                        "pfx_rcvd": 0,
                        "msg_rcvd": 0,
                        "msg_sent": 0
                    })
        else:
            # Phase-1 Default: Load instantly from local SQLite DB / Inventory
            cached_db_peers = self.db.get_latest_peer_snapshots()
            if cached_db_peers:
                for cp in cached_db_peers:
                    dev_id = cp.get("device_id")
                    dev_name = cp.get("device_name")
                    if device_filter and dev_id not in device_filter and dev_name not in device_filter:
                        continue
                    p_dict = dict(cp)
                    ip = p_dict.get("neighbor_ip")
                    meta = meta_map.get(f"{dev_id}:{ip}") or meta_map.get(ip, {})
                    p_dict["description"] = p_dict.get("description") or meta.get("description", "-")
                    all_peers.append(p_dict)
            else:
                # Fallback to configured inventory peers
                for dev in devices:
                    dev_id = dev.get("id")
                    dev_name = dev.get("name")
                    dev_vendor = dev.get("vendor")
                    if device_filter and dev_id not in device_filter and dev_name not in device_filter:
                        continue
                    for nbr in dev.get("provider_neighbors", []):
                        all_peers.append({
                            "device_id": dev_id,
                            "device_name": dev_name,
                            "vendor": dev_vendor,
                            "neighbor_ip": nbr.get("ip"),
                            "remote_as": nbr.get("asn", 0),
                            "provider": nbr.get("provider", "Custom"),
                            "description": nbr.get("description", ""),
                            "state": "Configured",
                            "uptime": "-",
                            "pfx_rcvd": 0,
                            "msg_rcvd": 0,
                            "msg_sent": 0
                        })

        # Apply filtering
        filtered_peers = []
        for peer_entry in all_peers:
            provider_name = peer_entry.get("provider", "")
            if provider_filter:
                is_unmapped = "(Unmapped)" in provider_name or provider_name.startswith("AS")
                if is_unmapped and "Unmapped Peers" in provider_filter:
                    pass
                elif provider_name not in provider_filter:
                    continue
            if status_filter and status_filter != "All":
                if status_filter == "Established" and peer_entry.get("state") != "Established":
                    continue
                if status_filter == "Down/Flapping" and peer_entry.get("state") == "Established":
                    continue
            filtered_peers.append(peer_entry)

        return filtered_peers

    def get_neighbor_routes(
        self,
        device_id: str,
        neighbor_ip: str,
        route_type: str = "received",
        simulation_mode: bool = True
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """Fetch received or advertised routes for a specific peer."""
        dev = self.dm.get_device(device_id)
        if not dev and not simulation_mode:
            return False, f"Device ID '{device_id}' not found.", []

        if simulation_mode:
            routes = get_simulated_neighbor_routes(neighbor_ip, route_type)
            raw = f"Simulation output for {route_type} routes on neighbor {neighbor_ip}"
            return True, raw, routes
        else:
            return get_live_neighbor_routes(dev, neighbor_ip, route_type)

    def search_prefix(
        self,
        prefix: str,
        simulation_mode: bool = False
    ) -> List[Dict[str, Any]]:
        """Phase-1 On-Demand Prefix Lookup: instant database search without background SSH bottlenecks."""
        results = []
        prefix_clean = prefix.strip()
        if not prefix_clean:
            return []

        if simulation_mode:
            devices = self.get_devices()
            for dev in devices:
                for nbr in dev.get("provider_neighbors", []):
                    ip = nbr.get("ip")
                    provider = nbr.get("provider")
                    routes = get_simulated_neighbor_routes(ip, "received")
                    for r in routes:
                        if prefix_clean in r.get("prefix", "") or r.get("prefix", "").startswith(prefix_clean):
                            as_path = r.get("as_path", "")
                            as_hops = len(as_path.split()) if as_path != "Direct" else 0
                            results.append({
                                "device": dev.get("name"),
                                "vendor": dev.get("vendor"),
                                "provider": provider,
                                "neighbor_ip": ip,
                                "prefix": r.get("prefix"),
                                "next_hop": r.get("next_hop"),
                                "metric": r.get("metric"),
                                "loc_pref": r.get("loc_pref"),
                                "as_path": as_path,
                                "as_hops": as_hops,
                                "best": r.get("best", False)
                            })
        else:
            # Query from local database instantaneously (sub-millisecond)
            db_records = self.db.get_prefix_history(prefix_clean)
            for rec in db_records:
                as_path = rec.get("as_path", "")
                as_hops = len(as_path.split()) if as_path != "Direct" else 0
                results.append({
                    "device": rec.get("device_name", ""),
                    "vendor": rec.get("vendor", ""),
                    "provider": rec.get("provider", ""),
                    "neighbor_ip": rec.get("neighbor_ip", ""),
                    "prefix": rec.get("prefix", ""),
                    "next_hop": rec.get("next_hop", ""),
                    "metric": rec.get("metric", "-"),
                    "loc_pref": rec.get("loc_pref", "-"),
                    "as_path": as_path,
                    "as_hops": as_hops,
                    "best": bool(rec.get("is_best", 0))
                })
        return results

    def collect_and_save_snapshot(self, simulation_mode: bool = True, note: str = "") -> int:
        """
        Poll all devices, gather peer sessions along with all received and advertised routes,
        and save everything to SQLite database.
        """
        devices = self.get_devices()
        peers = self.get_peers(simulation_mode=simulation_mode)
        all_routes = []

        for dev in devices:
            dev_id = dev.get("id")
            dev_name = dev.get("name")
            dev_vendor = dev.get("vendor")

            for nbr in dev.get("provider_neighbors", []):
                ip = nbr.get("ip")
                provider = nbr.get("provider")

                # Fetch received routes
                _, _, rcvd_routes = self.get_neighbor_routes(dev_id, ip, "received", simulation_mode)
                for r in rcvd_routes:
                    r_item = dict(r)
                    r_item["device_id"] = dev_id
                    r_item["device_name"] = dev_name
                    r_item["vendor"] = dev_vendor
                    r_item["neighbor_ip"] = ip
                    r_item["provider"] = provider
                    r_item["direction"] = "received"
                    all_routes.append(r_item)

                # Fetch advertised routes
                _, _, adv_routes = self.get_neighbor_routes(dev_id, ip, "advertised", simulation_mode)
                for a in adv_routes:
                    a_item = dict(a)
                    a_item["device_id"] = dev_id
                    a_item["device_name"] = dev_name
                    a_item["vendor"] = dev_vendor
                    a_item["neighbor_ip"] = ip
                    a_item["provider"] = provider
                    a_item["direction"] = "advertised"
                    all_routes.append(a_item)

        snapshot_id = self.db.record_snapshot(
            mode="simulation" if simulation_mode else "live",
            peers=peers,
            routes=all_routes,
            note=note or ("Live Hardware Snapshot" if not simulation_mode else "Simulated Poll Snapshot")
        )
        return snapshot_id
