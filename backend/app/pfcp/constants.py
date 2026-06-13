"""
PFCP Protocol Constants per 3GPP TS 29.244
"""
from enum import IntEnum

# PFCP Header constants
PFCP_VERSION = 1
PFCP_HEADER_LEN_NO_SEID = 8
PFCP_HEADER_LEN_WITH_SEID = 16

# UDP port
PFCP_PORT = 8805


class MessageType(IntEnum):
    """PFCP Message Types per TS 29.244 Table 7.3-1"""
    # Node-related messages
    HEARTBEAT_REQUEST = 1
    HEARTBEAT_RESPONSE = 2
    PFD_MANAGEMENT_REQUEST = 3
    PFD_MANAGEMENT_RESPONSE = 4
    ASSOCIATION_SETUP_REQUEST = 5
    ASSOCIATION_SETUP_RESPONSE = 6
    ASSOCIATION_UPDATE_REQUEST = 7
    ASSOCIATION_UPDATE_RESPONSE = 8
    ASSOCIATION_RELEASE_REQUEST = 9
    ASSOCIATION_RELEASE_RESPONSE = 10
    VERSION_NOT_SUPPORTED_RESPONSE = 11
    NODE_REPORT_REQUEST = 12
    NODE_REPORT_RESPONSE = 13
    SESSION_SET_DELETION_REQUEST = 14
    SESSION_SET_DELETION_RESPONSE = 15

    # Session-related messages
    SESSION_ESTABLISHMENT_REQUEST = 50
    SESSION_ESTABLISHMENT_RESPONSE = 51
    SESSION_MODIFICATION_REQUEST = 52
    SESSION_MODIFICATION_RESPONSE = 53
    SESSION_DELETION_REQUEST = 54
    SESSION_DELETION_RESPONSE = 55
    SESSION_REPORT_REQUEST = 56
    SESSION_REPORT_RESPONSE = 57

    # Additional messages
    FEATURE_PROVISION_REQUEST = 58
    FEATURE_PROVISION_RESPONSE = 59
    SESSION_ESTABLISHMENT_REQUEST_2 = 60
    SESSION_ESTABLISHMENT_RESPONSE_2 = 61

    @classmethod
    def get_name(cls, value: int) -> str:
        try:
            name = cls(value).name
        except ValueError:
            return f"Unknown ({value})"
        # PFCP-specific overrides for better readability
        overrides = {
            'PFD_MANAGEMENT_REQUEST': 'PFD Management Request',
            'PFD_MANAGEMENT_RESPONSE': 'PFD Management Response',
            'VERSION_NOT_SUPPORTED_RESPONSE': 'Version Not Supported Response',
            'SESSION_SET_DELETION_REQUEST': 'Session Set Deletion Request',
            'SESSION_SET_DELETION_RESPONSE': 'Session Set Deletion Response',
            'FEATURE_PROVISION_REQUEST': 'Feature Provision Request',
            'FEATURE_PROVISION_RESPONSE': 'Feature Provision Response',
        }
        if name in overrides:
            return overrides[name]
        return name.replace('_', ' ').title()


class IEType(IntEnum):
    """PFCP IE Types per 3GPP TS 29.244 Table 8.1.1-1"""
    # Group IEs
    CREATE_PDR = 1
    PDI = 2
    CREATE_FAR = 3
    FORWARDING_PARAMETERS = 4
    DUPLICATING_PARAMETERS = 5
    CREATE_URR = 6
    CREATE_QER = 7
    CREATED_PDR = 8
    UPDATE_PDR = 9
    UPDATE_FAR = 10
    UPDATE_FORWARDING_PARAMETERS = 11
    UPDATE_BAR = 12
    UPDATE_URR = 13
    UPDATE_QER = 14
    REMOVE_PDR = 15
    REMOVE_FAR = 16
    REMOVE_URR = 17
    REMOVE_QER = 18
    # Common IEs
    CAUSE = 19
    SOURCE_INTERFACE = 20
    F_TEID = 21
    NETWORK_INSTANCE = 22
    SDF_FILTER = 23
    APPLICATION_ID = 24
    GATE_STATUS = 25
    MBR = 26
    GBR = 27
    QER_CORRELATION_ID = 28
    PRECEDENCE = 29
    TRANSPORT_LEVEL_MARKING = 30
    VOLUME_THRESHOLD = 31
    TIME_THRESHOLD = 32
    MONITORING_TIME = 33
    SUBSEQUENT_VOLUME_THRESHOLD = 34
    SUBSEQUENT_TIME_THRESHOLD = 35
    INACTIVITY_DETECTION_TIME = 36
    REPORTING_TRIGGERS = 37
    REDIRECT_INFORMATION = 38
    REPORT_TYPE = 39
    OFFENDING_IE = 40
    FORWARDING_POLICY = 41
    DESTINATION_INTERFACE = 42
    UP_FUNCTION_FEATURES = 43
    APPLY_ACTION = 44
    DOWNLINK_DATA_SERVICE_INFORMATION = 45
    DOWNLINK_DATA_NOTIFICATION_DELAY = 46
    DL_BUFFERING_DURATION = 47
    DL_BUFFERING_SUGGESTED_PACKET_COUNT = 48
    PFCPSMREQ_FLAGS = 49
    PFCPSRRSP_FLAGS = 50
    LOAD_CONTROL_INFORMATION = 51
    SEQUENCE_NUMBER = 52
    METRIC = 53
    OVERLOAD_CONTROL_INFORMATION = 54
    TIMER = 55
    PACKET_DETECTION_RULE_ID = 56
    F_SEID = 57
    APPLICATION_IDS_PFD = 58
    PFD_CONTEXT = 59
    NODE_ID = 60
    PFD_CONTENTS = 61
    MEASUREMENT_METHOD = 62
    USAGE_REPORT_TRIGGER = 63
    MEASUREMENT_PERIOD = 64
    FQ_CSID = 65
    VOLUME_MEASUREMENT = 66
    DURATION_MEASUREMENT = 67
    APPLICATION_DETECTION_INFORMATION = 68
    TIME_OF_FIRST_PACKET = 69
    TIME_OF_LAST_PACKET = 70
    QUOTA_HOLDING_TIME = 71
    DROPPED_DL_TRAFFIC_THRESHOLD = 72
    LOGGING = 73
    USER_PLANE_INACTIVITY_TIMER = 74
    START_TIME = 75
    END_TIME = 76
    MULTIPLIER = 77
    AGGREGATED_URR = 78
    USAGE_REPORT_SESSION_DELETION_RESPONSE = 79
    QUERY_URR = 80
    URR_ID = 81
    USAGE_URR_ID = 82
    DOWNLINK_DATA_REPORT = 84
    OUTER_HEADER_CREATION = 85
    CREATE_BAR = 86
    UPDATE_BAR_SESSION_MODIFICATION = 87
    BAR_ID = 88
    CP_FUNCTION_FEATURES = 89
    USAGE_INFORMATION = 90
    APPLICATION_INSTANCE_ID = 91
    FLOW_INFORMATION = 92
    UE_IP_ADDRESS = 93
    PACKET_RATE = 94
    OUTER_HEADER_REMOVAL = 95
    RECOVERY_TIME_STAMP = 96
    DL_FLOW_LEVEL_MARKING = 97
    HEADER_ENRICHMENT = 98
    ERROR_INDICATION_REPORT = 99
    MEASUREMENT_INFORMATION = 100
    NODE_REPORT_TYPE = 101
    USER_PLANE_PATH_FAILURE_REPORT = 102
    REMOTE_GTP_U_PEER = 103
    UR_SEQN = 104
    UP_FUNCTION_FEATURES_2 = 105
    ACTIVATE_PREDEFINED_RULES = 106
    DEACTIVATE_PREDEFINED_RULES = 107
    FAR_ID = 108
    QER_ID = 109
    OCI_FLAGS = 110
    PFCP_ASSOCIATION_RELEASE_REQUEST = 111
    GRACEFUL_RELEASE_PERIOD = 112
    PDN_TYPE = 113
    FAILED_RULE_ID = 114
    TIME_QUOTA_MECHANISM = 115
    USER_PLANE_IP_RESOURCE_INFORMATION = 116
    USER_PLANE_INACTIVITY_TIMER_2 = 117
    PFCP_SESSION_RETENTION_INFORMATION = 119
    SESSION_INDEX = 120

    @classmethod
    def get_name(cls, value: int) -> str:
        try:
            name = cls(value).name
        except ValueError:
            return f"Unknown IE ({value})"
        # Apply PFCP-specific display name overrides
        overrides = {
            'NODE_ID': 'Node ID', 'F_SEID': 'F-SEID', 'F_TEID': 'F-TEID',
            'CREATE_PDR': 'Create PDR', 'CREATE_FAR': 'Create FAR',
            'CREATE_URR': 'Create URR', 'CREATE_QER': 'Create QER',
            'CREATE_BAR': 'Create BAR', 'CREATED_PDR': 'Created PDR',
            'UPDATE_PDR': 'Update PDR', 'UPDATE_FAR': 'Update FAR',
            'UPDATE_URR': 'Update URR', 'UPDATE_QER': 'Update QER',
            'UPDATE_BAR': 'Update BAR', 'UPDATE_BAR_SESSION_MODIFICATION': 'Update BAR',
            'REMOVE_PDR': 'Remove PDR', 'REMOVE_FAR': 'Remove FAR',
            'REMOVE_URR': 'Remove URR', 'REMOVE_QER': 'Remove QER',
            'PDR_ID': 'PDR ID', 'FAR_ID': 'FAR ID', 'QER_ID': 'QER ID',
            'URR_ID': 'URR ID', 'BAR_ID': 'BAR ID',
            'UE_IP_ADDRESS': 'UE IP Address',
            'SDF_FILTER': 'SDF Filter',
            'PDI': 'PDI',
            'MBR': 'MBR', 'GBR': 'GBR', 'QFI': 'QFI', 'RQI': 'RQI',
            'OCI_FLAGS': 'OCI Flags',
            'PFCPSMREQ_FLAGS': 'PFCPSMReq Flags',
            'PFCPSRRSP_FLAGS': 'PFCPSRRsp Flags',
            'PFCP_ASSOCIATION_RELEASE_REQUEST': 'PFCP Association Release Request',
            'PFCP_SESSION_RETENTION_INFORMATION': 'PFCP Session Retention Information',
            'CP_FUNCTION_FEATURES': 'CP Function Features',
            'UP_FUNCTION_FEATURES': 'UP Function Features',
            'UP_FUNCTION_FEATURES_2': 'UP Function Features 2',
            'USAGE_REPORT_TRIGGER': 'Usage Report Trigger',
            'VOLUME_MEASUREMENT': 'Volume Measurement',
            'DURATION_MEASUREMENT': 'Duration Measurement',
            'START_TIME': 'Start Time', 'END_TIME': 'End Time',
            'RECOVERY_TIME_STAMP': 'Recovery Time Stamp',
            'OUTER_HEADER_CREATION': 'Outer Header Creation',
            'OUTER_HEADER_REMOVAL': 'Outer Header Removal',
            'UR_SEQN': 'UR-SEQN',
            'APPLICATION_DETECTION_INFORMATION': 'Application Detection Information',
            'DOWNLINK_DATA_REPORT': 'Downlink Data Report',
            'USAGE_REPORT_SESSION_ESTABLMENT': 'Usage Report (Session Establishment Response)',
            'USAGE_REPORT_SESSION_MODIFICATION': 'Usage Report (Session Modification Response)',
            'USAGE_REPORT_SESSION_DELETION_RESPONSE': 'Usage Report (Session Deletion Response)',
            'USAGE_REPORT_SESSION_REPORT': 'Usage Report (Session Report Request)',
        }
        if name in overrides:
            return overrides[name]
        return name.replace('_', ' ').title()


# Group IEs that contain sub-IEs
GROUP_IE_TYPES = {
    IEType.CREATE_PDR,
    IEType.PDI,
    IEType.CREATE_FAR,
    IEType.FORWARDING_PARAMETERS,
    IEType.DUPLICATING_PARAMETERS,
    IEType.CREATE_URR,
    IEType.CREATE_QER,
    IEType.CREATED_PDR,
    IEType.UPDATE_PDR,
    IEType.UPDATE_FAR,
    IEType.UPDATE_FORWARDING_PARAMETERS,
    IEType.UPDATE_URR,
    IEType.UPDATE_QER,
    IEType.REMOVE_PDR,
    IEType.REMOVE_FAR,
    IEType.REMOVE_URR,
    IEType.REMOVE_QER,
    IEType.LOAD_CONTROL_INFORMATION,
    IEType.OVERLOAD_CONTROL_INFORMATION,
    IEType.APPLICATION_IDS_PFD,
    IEType.PFD_CONTEXT,
    IEType.DOWNLINK_DATA_REPORT,
    IEType.AGGREGATED_URR,
    IEType.CREATE_BAR,
    IEType.USER_PLANE_PATH_FAILURE_REPORT,
    IEType.UPDATE_BAR_SESSION_MODIFICATION,
    IEType.APPLICATION_DETECTION_INFORMATION,
    IEType.ERROR_INDICATION_REPORT,
    IEType.QUERY_URR,
    IEType.USAGE_REPORT_SESSION_DELETION_RESPONSE,
}

# Editable fields (field_path -> type)
EDITABLE_FIELDS = {
    "header.seid": "uint64",
    "header.sequence_number": "uint24",
    "pdr_id": "uint16",
    "precedence": "uint32",
    "far_id": "uint32",
    "qer_id": "uint32",
    "urr_id": "uint32",
    "bar_id": "uint8",
    "f_teid.teid": "uint32",
    "f_teid.ipv4_address": "ipv4",
    "f_teid.ipv6_address": "ipv6",
    "ue_ip_address.ipv4": "ipv4",
    "ue_ip_address.ipv6": "ipv6",
    "outer_header_creation.teid": "uint32",
    "outer_header_creation.ipv4_address": "ipv4",
    "apply_action": "flags",
    "gate_status.ul_gate": "enum",
    "gate_status.dl_gate": "enum",
    "mbr.ul_mbr": "bitrate",
    "mbr.dl_mbr": "bitrate",
    "gbr.ul_gbr": "bitrate",
    "gbr.dl_gbr": "bitrate",
    "network_instance": "string",
    "sdf_filter": "string",
    "application_id": "string",
    "source_interface": "enum",
    "destination_interface": "enum",
}

# Source/Destination Interface values
INTERFACE_VALUES = {
    0: "Access",
    1: "Core",
    2: "SGi-LAN/N6-LAN",
    3: "CP-function",
    4: "LI Function",
}

# Gate Status values
GATE_STATUS_VALUES = {
    0: "OPEN",
    1: "CLOSED",
    2: "CLOSED_IDLE",
    3: "OPEN_IDLE",
}

# Apply Action flags
APPLY_ACTION_FLAGS = {
    "DROP": 0x01,
    "FORWARD": 0x02,
    "BUFFER": 0x04,
    "NOTIFY_CP": 0x08,
    "DUPLICATE": 0x10,
}

# Node ID types
NODE_ID_TYPES = {
    0: "IPv4",
    1: "IPv6",
    2: "FQDN",
}

# Cause values
CAUSE_VALUES = {
    0: "Reserved",
    1: "Request accepted(success)",
    64: "Request rejected",
    65: "Session context not found",
    66: "Mandatory IE missing",
    67: "Conditional IE missing",
    68: "Invalid length",
    69: "Mandatory IE incorrect",
    70: "Invalid forward forwarding policy",
    71: "Invalid F-TEID allocation option",
    72: "No established Sx Association",
    73: "Rule creation/modification failure",
    74: "PFCP entity in congestion",
    75: "No resources available",
    76: "Service not supported",
    77: "System failure",
    78: "Redirection requested",
}

# Outer Header Removal descriptions
OUTER_HEADER_REMOVAL_DESCRIPTIONS = {
    0: "GTP-U/UDP/IPv4",
    1: "GTP-U/UDP/IPv6",
    2: "UDP/IPv4",
    3: "UDP/IPv6",
    4: "IPv4",
    5: "IPv6",
    6: "GTP-U/UDP/IP",
}

# Usage Report Trigger flag definitions (TS 29.244 8.2.41)
USAGE_REPORT_TRIGGER_BYTE1 = [
    ("IMMER (Immediate Report)", 7),
    ("DROTH (Dropped DL Traffic Threshold)", 6),
    ("STOPT (Stop of Traffic)", 5),
    ("START (Start of Traffic)", 4),
    ("QUHTI (Quota Holding Time)", 3),
    ("TIMTH (Time Threshold)", 2),
    ("VOLTH (Volume Threshold)", 1),
    ("PERIO (Periodic Reporting)", 0),
]

USAGE_REPORT_TRIGGER_BYTE2 = [
    ("EVETH (Event Threshold)", 7),
    ("MACAR (MAC Addresses Reporting)", 6),
    ("ENVCL (Envelope Closure)", 5),
    ("MONIT (Monitoring Time)", 4),
    ("TERMR (Termination Report)", 3),
    ("LIUSA (Linked Usage Reporting)", 2),
    ("TIMQU (Time Quota)", 1),
    ("VOLQU (Volume Quota)", 0),
]

USAGE_REPORT_TRIGGER_BYTE3 = [
    ("UPINT (User Plane Inactivity Timer)", 5),
    ("EMRRE (End Marker Reception REport)", 4),
    ("QUVTI (Quota Validity Time)", 3),
    ("IPMJL (IP Multicast Join/Leave)", 2),
    ("TEBUR (Termination By UP function Report)", 1),
    ("EVEQU (Event Quota)", 0),
]

# Volume Measurement flag definitions (TS 29.244 8.2.44)
VOLUME_MEASUREMENT_FLAGS = [
    ("DLNOP", 1), ("ULNOP", 2), ("TONOP", 3),
    ("DLVOL", 4), ("ULVOL", 5), ("TOVOL", 6),
]

# FAR ID / QER ID / URR ID allocation type
ALLOCATION_TYPE_NAMES = {
    0: "Dynamic by CP",
    1: "Predefined",
}
