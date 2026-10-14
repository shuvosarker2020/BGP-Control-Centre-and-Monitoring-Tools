"""Database manager for storing BGP received/advertised routes and tracking router trends."""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "bgp_history.db")

class BGPDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self._seed_sample_history_if_empty()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Snapshots table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                mode TEXT NOT NULL,
                note TEXT,
                total_peers INTEGER DEFAULT 0,
                total_received_routes INTEGER DEFAULT 0,
                total_advertised_routes INTEGER DEFAULT 0
            )
            """)

            # Peer history snapshot table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS peer_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                device_id TEXT NOT NULL,
                device_name TEXT NOT NULL,
                vendor TEXT NOT NULL,
                neighbor_ip TEXT NOT NULL,
                remote_as INTEGER,
                provider TEXT,
                state TEXT,
                uptime TEXT,
                pfx_rcvd INTEGER DEFAULT 0,
                msg_rcvd INTEGER DEFAULT 0,
                msg_sent INTEGER DEFAULT 0,
                FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
            )
            """)

            # Route history snapshot table (both received and advertised)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS route_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                device_id TEXT NOT NULL,
                device_name TEXT NOT NULL,
                vendor TEXT NOT NULL,
                neighbor_ip TEXT NOT NULL,
                provider TEXT,
                direction TEXT NOT NULL, -- 'received' or 'advertised'
                prefix TEXT NOT NULL,
                next_hop TEXT,
                as_path TEXT,
                as_hops INTEGER DEFAULT 0,
                metric TEXT,
                loc_pref TEXT,
                weight TEXT,
                origin TEXT,
                is_best BOOLEAN DEFAULT 0,
                FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
            )
            """)

            # Indexes for high performance queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_route_snapshot_id ON route_snapshots(snapshot_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_route_prefix ON route_snapshots(prefix)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_route_provider ON route_snapshots(provider)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_route_direction ON route_snapshots(direction)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_peer_snapshot_id ON peer_snapshots(snapshot_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_ts ON snapshots(timestamp)")
            conn.commit()

    def record_snapshot(
        self,
        mode: str,
        peers: List[Dict[str, Any]],
        routes: List[Dict[str, Any]],
        note: str = "",
        custom_timestamp: Optional[str] = None
    ) -> int:
        """Store a full snapshot of peers and routes."""
        ts = custom_timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_rcvd = sum(1 for r in routes if r.get("direction") == "received")
        total_adv = sum(1 for r in routes if r.get("direction") == "advertised")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO snapshots (timestamp, mode, note, total_peers, total_received_routes, total_advertised_routes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ts, mode, note, len(peers), total_rcvd, total_adv))
            snapshot_id = cursor.lastrowid

            # Insert peer snapshots
            peer_rows = []
            for p in peers:
                peer_rows.append((
                    snapshot_id,
                    ts,
                    p.get("device_id", ""),
                    p.get("device_name", ""),
                    p.get("vendor", ""),
                    p.get("neighbor_ip", ""),
                    p.get("remote_as", 0),
                    p.get("provider", ""),
                    p.get("state", ""),
                    p.get("uptime", ""),
                    p.get("pfx_rcvd", 0),
                    p.get("msg_rcvd", 0),
                    p.get("msg_sent", 0)
                ))

            cursor.executemany("""
                INSERT INTO peer_snapshots (
                    snapshot_id, timestamp, device_id, device_name, vendor, neighbor_ip,
                    remote_as, provider, state, uptime, pfx_rcvd, msg_rcvd, msg_sent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, peer_rows)

            # Insert route snapshots
            route_rows = []
            for r in routes:
                as_path = str(r.get("as_path", ""))
                as_hops = len(as_path.split()) if as_path and as_path != "Direct" else 0
                route_rows.append((
                    snapshot_id,
                    ts,
                    r.get("device_id", ""),
                    r.get("device_name", ""),
                    r.get("vendor", ""),
                    r.get("neighbor_ip", ""),
                    r.get("provider", ""),
                    r.get("direction", "received"),
                    r.get("prefix", ""),
                    r.get("next_hop", ""),
                    as_path,
                    as_hops,
                    str(r.get("metric", "-")),
                    str(r.get("loc_pref", "-")),
                    str(r.get("weight", "-")),
                    str(r.get("origin", "i")),
                    1 if r.get("best", False) else 0
                ))

            cursor.executemany("""
                INSERT INTO route_snapshots (
                    snapshot_id, timestamp, device_id, device_name, vendor, neighbor_ip,
                    provider, direction, prefix, next_hop, as_path, as_hops,
                    metric, loc_pref, weight, origin, is_best
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, route_rows)

            conn.commit()
            return snapshot_id

    def get_snapshots(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM snapshots ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_snapshot_by_id(self, snapshot_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_latest_peer_snapshots(self, snapshot_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve peer session snapshots from latest or specified snapshot."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if snapshot_id is None:
                cursor.execute("SELECT id FROM snapshots ORDER BY id DESC LIMIT 1")
                row = cursor.fetchone()
                if not row:
                    return []
                snapshot_id = row[0]

            cursor.execute("SELECT * FROM peer_snapshots WHERE snapshot_id = ?", (snapshot_id,))
            return [dict(r) for r in cursor.fetchall()]

    def delete_snapshot(self, snapshot_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))
            conn.commit()
            return True

    def get_route_snapshots(
        self,
        snapshot_id: int,
        direction: Optional[str] = None,
        provider: Optional[str] = None,
        neighbor_ip: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve stored routes for a given snapshot with optional filters."""
        query = "SELECT * FROM route_snapshots WHERE snapshot_id = ?"
        params = [snapshot_id]

        if direction:
            query += " AND direction = ?"
            params.append(direction)
        if provider and provider != "All":
            query += " AND provider = ?"
            params.append(provider)
        if neighbor_ip and neighbor_ip != "All":
            query += " AND neighbor_ip = ?"
            params.append(neighbor_ip)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_historical_route_trend(
        self,
        provider: Optional[str] = None,
        direction: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Aggregate route counts across snapshots to show trends over time.
        """
        query = """
            SELECT 
                s.id as snapshot_id,
                s.timestamp,
                r.provider,
                r.direction,
                COUNT(r.id) as route_count,
                COUNT(DISTINCT r.prefix) as unique_prefixes
            FROM route_snapshots r
            JOIN snapshots s ON r.snapshot_id = s.id
            WHERE 1=1
        """
        params = []
        if provider and provider != "All":
            query += " AND r.provider = ?"
            params.append(provider)
        if direction and direction != "All":
            query += " AND r.direction = ?"
            params.append(direction)

        query += " GROUP BY s.id, s.timestamp, r.provider, r.direction ORDER BY s.id ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_historical_peer_trend(
        self,
        provider: Optional[str] = None,
        neighbor_ip: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Aggregate peer received prefixes and states over time across snapshots.
        """
        query = """
            SELECT 
                s.id as snapshot_id,
                s.timestamp,
                p.device_name,
                p.neighbor_ip,
                p.provider,
                p.state,
                p.pfx_rcvd
            FROM peer_snapshots p
            JOIN snapshots s ON p.snapshot_id = s.id
            WHERE 1=1
        """
        params = []
        if provider and provider != "All":
            query += " AND p.provider = ?"
            params.append(provider)
        if neighbor_ip and neighbor_ip != "All":
            query += " AND p.neighbor_ip = ?"
            params.append(neighbor_ip)

        query += " ORDER BY s.id ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def compare_snapshots(self, old_snapshot_id: int, new_snapshot_id: int) -> Dict[str, Any]:
        """
        Compare routes between two snapshots to detect changes:
        - Added routes
        - Withdrawn/Removed routes
        - Modified routes (changed AS-Path, Next Hop, LocPref, MED)
        """
        old_routes = self.get_route_snapshots(old_snapshot_id)
        new_routes = self.get_route_snapshots(new_snapshot_id)

        # Map by unique key: (direction, neighbor_ip, prefix)
        old_map = {(r["direction"], r["neighbor_ip"], r["prefix"]): r for r in old_routes}
        new_map = {(r["direction"], r["neighbor_ip"], r["prefix"]): r for r in new_routes}

        added = []
        withdrawn = []
        modified = []

        # Find added and modified
        for key, new_item in new_map.items():
            if key not in old_map:
                added.append(new_item)
            else:
                old_item = old_map[key]
                # Check for modifications
                changes = []
                if new_item.get("as_path") != old_item.get("as_path"):
                    changes.append(f"AS Path: '{old_item.get('as_path')}' -> '{new_item.get('as_path')}'")
                if new_item.get("next_hop") != old_item.get("next_hop"):
                    changes.append(f"Next Hop: '{old_item.get('next_hop')}' -> '{new_item.get('next_hop')}'")
                if new_item.get("metric") != old_item.get("metric"):
                    changes.append(f"MED: '{old_item.get('metric')}' -> '{new_item.get('metric')}'")
                if new_item.get("loc_pref") != old_item.get("loc_pref"):
                    changes.append(f"LocPref: '{old_item.get('loc_pref')}' -> '{new_item.get('loc_pref')}'")
                if new_item.get("is_best") != old_item.get("is_best"):
                    changes.append(f"Best: '{old_item.get('is_best')}' -> '{new_item.get('is_best')}'")

                if changes:
                    mod_entry = dict(new_item)
                    mod_entry["change_summary"] = ", ".join(changes)
                    mod_entry["old_as_path"] = old_item.get("as_path")
                    mod_entry["old_next_hop"] = old_item.get("next_hop")
                    modified.append(mod_entry)

        # Find withdrawn
        for key, old_item in old_map.items():
            if key not in new_map:
                withdrawn.append(old_item)

        return {
            "old_snapshot_id": old_snapshot_id,
            "new_snapshot_id": new_snapshot_id,
            "added_count": len(added),
            "withdrawn_count": len(withdrawn),
            "modified_count": len(modified),
            "added": added,
            "withdrawn": withdrawn,
            "modified": modified
        }

    def get_prefix_history(self, prefix: str) -> List[Dict[str, Any]]:
        """Find all historical records of a specific prefix over time."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    r.*,
                    s.timestamp as snapshot_time
                FROM route_snapshots r
                JOIN snapshots s ON r.snapshot_id = s.id
                WHERE r.prefix LIKE ?
                ORDER BY s.id DESC
            """, (f"%{prefix.strip()}%",))
            return [dict(row) for row in cursor.fetchall()]

    def _seed_sample_history_if_empty(self):
        """Seed 3 historical snapshots if database is completely new so trend charts display immediately."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM snapshots")
            count = cursor.fetchone()[0]
            if count > 0:
                return

        # Let's import mock data from simulator
        from core.simulator import MOCK_NEIGHBOR_ROUTES
        from core.device_manager import DeviceManager

        dm = DeviceManager()
        devices = dm.load_devices()

        now = datetime.now()
        timestamps = [
            (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            now.strftime("%Y-%m-%d %H:%M:%S")
        ]

        # Seed 3 sequential snapshots representing baseline, slight change, and current
        for idx, ts in enumerate(timestamps):
            all_peers = []
            all_routes = []

            for dev in devices:
                for nbr in dev.get("provider_neighbors", []):
                    ip = nbr.get("ip")
                    asn = nbr.get("asn")
                    provider = nbr.get("provider")

                    # Base pfx
                    pfx_count = 940000 + (idx * 2500) if "Transit" in nbr.get("description", "") else 1400 + (idx * 50)
                    all_peers.append({
                        "device_id": dev.get("id"),
                        "device_name": dev.get("name"),
                        "vendor": dev.get("vendor"),
                        "neighbor_ip": ip,
                        "remote_as": asn,
                        "provider": provider,
                        "state": "Established",
                        "uptime": f"{idx+2}d04h",
                        "pfx_rcvd": pfx_count,
                        "msg_rcvd": 50000 * (idx + 1),
                        "msg_sent": 50000 * (idx + 1)
                    })

                    # Routes
                    routes_dict = MOCK_NEIGHBOR_ROUTES.get(ip, {})
                    rcvd = routes_dict.get("received", [])
                    adv = routes_dict.get("advertised", [])

                    for r in rcvd:
                        r_copy = dict(r)
                        r_copy["device_id"] = dev.get("id")
                        r_copy["device_name"] = dev.get("name")
                        r_copy["vendor"] = dev.get("vendor")
                        r_copy["neighbor_ip"] = ip
                        r_copy["provider"] = provider
                        r_copy["direction"] = "received"
                        
                        # Introduce a realistic trend evolution
                        if idx == 0 and r_copy.get("prefix") == "104.16.0.0/12" and "Lumen" in provider:
                            # In baseline 2 days ago, AS path had an extra prepend
                            r_copy["as_path"] = "3356 3356 13335"
                        if idx == 0 and r_copy.get("prefix") == "199.232.0.0/16":
                            # This route was not present 2 days ago, added yesterday
                            continue
                        all_routes.append(r_copy)

                    for a in adv:
                        a_copy = dict(a)
                        a_copy["device_id"] = dev.get("id")
                        a_copy["device_name"] = dev.get("name")
                        a_copy["vendor"] = dev.get("vendor")
                        a_copy["neighbor_ip"] = ip
                        a_copy["provider"] = provider
                        a_copy["direction"] = "advertised"
                        all_routes.append(a_copy)

            self.record_snapshot(
                mode="simulation",
                peers=all_peers,
                routes=all_routes,
                note=f"Automated Snapshot (T-{2-idx}d)",
                custom_timestamp=ts
            )
