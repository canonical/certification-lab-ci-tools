import logging

formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)-8s %(name)s.%(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
package_logger = logging.getLogger(__name__)
package_logger.setLevel(logging.INFO)
# package_logger.setLevel(logging.DEBUG)
if not package_logger.handlers:
    package_logger.addHandler(console_handler)
