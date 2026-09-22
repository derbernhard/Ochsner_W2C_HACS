DOMAIN = "ochsner_w2c"
PLATFORMS = ["sensor", "select", "switch", "binary_sensor", "number"]
CONF_W2C_HOST = "w2c_host"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MQTT_ENABLED = "mqtt_enabled"
CONF_MQTT_BASE_TOPIC = "mqtt_base_topic"
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_MQTT_BASE_TOPIC = "web2com"

OIDS = [
    "/1/2/4/119/1",
    "/1/2/4/119/3",
    "/1/2/4/119/7",
    "/1/2/4/119/0",
    "/1/2/4/107/0",
    "/1/2/7/121/1",
    "/1/2/7/121/2",
    "/1/2/7/121/0",
    "/1/2/7/107/0",
]

# Warmwasser-Boost
OID_WW_MODE = "/1/2/7/107/0"
OID_WW_SET = "/1/2/7/121/2"
OID_WW_ACTUAL = "/1/2/7/121/1"

MODE_WW_AUTO = 1
MODE_WW_NORMAL = 2

DEFAULT_BOOST_TARGET = 50.0
