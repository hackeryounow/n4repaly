"""
Configuration loader for N4Relay
Reads config from config/n4replay.yaml
"""
import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RelayConfig:
    listen_addr: str = "0.0.0.0"
    listen_port: int = 8805
    target_addr: str = "upf"
    target_port: int = 8805
    # NodeID to use when rewriting UPF responses for SMF compatibility.
    # Should match the nodeID configured in SMF's userplaneInformation.upNodes.UPF.nodeID
    smf_upf_node_id: str = ""  # empty = no rewriting


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8080


@dataclass
class InterceptConfig:
    enabled: bool = False
    max_held: int = 100


@dataclass
class BufferConfig:
    max_packets: int = 5000


@dataclass
class QueueConfig:
    max_size: int = 10000    # Max packets in processing queue
    workers: int = 4         # Number of async worker tasks


@dataclass
class AppConfig:
    relay: RelayConfig = field(default_factory=RelayConfig)
    web: WebConfig = field(default_factory=WebConfig)
    intercept: InterceptConfig = field(default_factory=InterceptConfig)
    buffer: BufferConfig = field(default_factory=BufferConfig)
    queue: QueueConfig = field(default_factory=QueueConfig)


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file"""
    if config_path is None:
        # Default config path
        config_path = os.environ.get(
            "N4RELAY_CONFIG",
            str(Path(__file__).parent.parent.parent / "config" / "n4replay.yaml")
        )

    config = AppConfig()

    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f) or {}

        if "relay" in data:
            r = data["relay"]
            config.relay = RelayConfig(
                listen_addr=r.get("listen_addr", "0.0.0.0"),
                listen_port=r.get("listen_port", 8805),
                target_addr=r.get("target_addr", "upf"),
                target_port=r.get("target_port", 8805),
                smf_upf_node_id=r.get("smf_upf_node_id", ""),
            )

        if "web" in data:
            w = data["web"]
            config.web = WebConfig(
                host=w.get("host", "0.0.0.0"),
                port=w.get("port", 8080),
            )

        if "intercept" in data:
            i = data["intercept"]
            config.intercept = InterceptConfig(
                enabled=i.get("enabled", False),
                max_held=i.get("max_held", 100),
            )

        if "buffer" in data:
            b = data["buffer"]
            config.buffer = BufferConfig(
                max_packets=b.get("max_packets", 5000),
            )

        if "queue" in data:
            q = data["queue"]
            config.queue = QueueConfig(
                max_size=q.get("max_size", 10000),
                workers=q.get("workers", 4),
            )
    else:
        print(f"[WARNING] Config file not found: {config_path}, using defaults")

    return config
