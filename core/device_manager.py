import os
import yaml
from typing import List, Dict, Any, Optional

INVENTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "inventory", "devices.yaml")

class DeviceManager:
    """Manages router inventory, credentials, and provider-neighbor mappings."""

    def __init__(self, filepath: str = INVENTORY_FILE):
        self.filepath = filepath
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", encoding="utf-8") as f:
                yaml.safe_dump({"devices": []}, f)

    def load_devices(self) -> List[Dict[str, Any]]:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if not data or "devices" not in data:
                    return []
                return data["devices"]
        except Exception as e:
            print(f"Error loading device inventory: {e}")
            return []

    def save_devices(self, devices: List[Dict[str, Any]]) -> bool:
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                yaml.safe_dump({"devices": devices}, f, default_flow_style=False, sort_keys=False)
            return True
        except Exception as e:
            print(f"Error saving device inventory: {e}")
            return False

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        devices = self.load_devices()
        for dev in devices:
            if dev.get("id") == device_id or dev.get("name") == device_id:
                return dev
        return None

    def upsert_device(self, device_data: Dict[str, Any]) -> bool:
        devices = self.load_devices()
        idx = next((i for i, d in enumerate(devices) if d.get("id") == device_data.get("id")), -1)
        if idx >= 0:
            devices[idx] = device_data
        else:
            devices.append(device_data)
        return self.save_devices(devices)

    def delete_device(self, device_id: str) -> bool:
        devices = self.load_devices()
        devices = [d for d in devices if d.get("id") != device_id]
        return self.save_devices(devices)

    def get_all_providers(self) -> List[str]:
        """Extract unique provider names from all device neighbor configurations."""
        devices = self.load_devices()
        providers = set()
        for dev in devices:
            for nbr in dev.get("provider_neighbors", []):
                prov = nbr.get("provider")
                if prov:
                    providers.add(prov)
        providers.add("Unmapped Peers")
        return sorted(list(providers))

    def update_device_neighbors_from_live(self, device_id: str, peers: List[Dict[str, Any]]) -> bool:
        """Auto-populate discovered BGP neighbors into device inventory."""
        devices = self.load_devices()
        updated = False
        for dev in devices:
            if dev.get("id") == device_id or dev.get("name") == device_id:
                if "provider_neighbors" not in dev or not dev["provider_neighbors"]:
                    dev["provider_neighbors"] = []
                existing_ips = {n.get("ip") for n in dev["provider_neighbors"]}
                for p in peers:
                    ip = p.get("neighbor_ip")
                    if ip and ip not in existing_ips:
                        dev["provider_neighbors"].append({
                            "ip": ip,
                            "asn": p.get("remote_as", 0),
                            "provider": f"AS{p.get('remote_as')}_Peer",
                            "description": f"Auto-discovered live BGP peer"
                        })
                        existing_ips.add(ip)
                        updated = True
        if updated:
            return self.save_devices(devices)
        return False

    def get_neighbor_meta_map(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns a mapping from neighbor IP (or device_id:ip) to provider metadata.
        Key can be just neighbor IP or '{device_id}:{ip}'.
        """
        devices = self.load_devices()
        mapping = {}
        for dev in devices:
            dev_id = dev.get("id")
            for nbr in dev.get("provider_neighbors", []):
                ip = nbr.get("ip")
                if ip:
                    meta = {
                        "provider": nbr.get("provider", "Unknown Provider"),
                        "asn": nbr.get("asn", 0),
                        "description": nbr.get("description", ""),
                        "device_id": dev_id,
                        "device_name": dev.get("name")
                    }
                    mapping[f"{dev_id}:{ip}"] = meta
                    mapping[ip] = meta
        return mapping

    def add_device_neighbor(self, device_id: str, neighbor_data: Dict[str, Any]) -> bool:
        """Add a new provider neighbor to a specific device."""
        devices = self.load_devices()
        for dev in devices:
            if dev.get("id") == device_id or dev.get("name") == device_id:
                if "provider_neighbors" not in dev:
                    dev["provider_neighbors"] = []
                # Check for duplicates
                ip = neighbor_data.get("ip")
                for existing in dev["provider_neighbors"]:
                    if existing.get("ip") == ip:
                        existing.update(neighbor_data)
                        return self.save_devices(devices)
                dev["provider_neighbors"].append(neighbor_data)
                return self.save_devices(devices)
        return False

    def delete_device_neighbor(self, device_id: str, neighbor_ip: str) -> bool:
        """Remove a provider neighbor from a specific device."""
        devices = self.load_devices()
        for dev in devices:
            if dev.get("id") == device_id or dev.get("name") == device_id:
                if "provider_neighbors" in dev:
                    dev["provider_neighbors"] = [n for n in dev["provider_neighbors"] if n.get("ip") != neighbor_ip]
                    return self.save_devices(devices)
        return False
