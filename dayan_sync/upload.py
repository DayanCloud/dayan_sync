"""Upload models.

Upload the scene's configuration file and asset file.

"""

# Import built-in modules
import configparser
import os
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Import local modules
from dayan_sync.transfer import RayvisionTransfer
from dayan_sync.constants import TRANSFER_LOG, RENDERFARM_SDK, WINDOWS_LOCAL_ENV, LINUX_LOCAL_ENV, RAYVISION_DB
from dayan_sync.exception import RayvisionError, UnsupportedDatabaseError
from dayan_sync.utils import create_transfer_params, get_share_info
from dayan_sync.utils import read_ini_config
from dayan_sync.utils import run_cmd
from dayan_sync.utils import str2unicode
from dayan_sync.utils import upload_retry
from dayan_sync.constants import PACKAGE_NAME
from rayvision_log import init_logger

class RayvisionUpload(object):
    """Upload files.

    Upload configuration files and asset files.

    """

    def __init__(self, api,
                 db_config_path=None,
                 transports_json="",
                 transmitter_exe="",
                 automatic_line=False,
                 internet_provider="",
                 logger=None,
                 log_folder=None,
                 log_name=None,
                 log_level="DEBUG"
                 ):
        """Initialize instance.

        Args:
            api (object): rayvision api object.
            db_config_path (string): Customize db_config.ini absolute path.
            transports_json (string): Customize the absolute path of the transfer configuration file.
            transmitter_exe (string): Customize the absolute path of the transfer execution file.
            automatic_line (bool): Whether to automatically obtain the transmission line, the default is "False"
            internet_provider (string): Network provider.
            logger (object): Customize log object.
            log_folder (string): Customize the absolute path of the folder where logs are stored.
            log_name (string): Custom log file name, the system user name will be searched by default.
            log_level (string):  Set log level, example: "DEBUG","INFO","WARNING","ERROR"
        """
        self.logger = logger
        if not self.logger:
            init_logger(PACKAGE_NAME, log_folder, log_name)
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(level=log_level.upper())

        params = create_transfer_params(api)
        params["transports_json"] = transports_json
        params["transmitter_exe"] = transmitter_exe
        params["automatic_line"] = automatic_line
        params["internet_provider"] = internet_provider
        self.api = api
        self.trans = RayvisionTransfer(api, **params)

        # load db config ini
        self.transfer_log_path, self.redis_config, self.sqlite_config, self.database_config = \
            self.load_db_config(db_config_path)

        custom_db_path = self.database_config.get("db_path")
        db_dir = self._check_and_mk(custom_db_path)
        self.check_transfer_log_path(self.transfer_log_path)
        self.db_ini = os.path.join(db_dir, 'db_ini')
        self._db = os.path.join(db_dir, 'db')

    def check_transfer_log_path(self, transfer_log_path):
        """Check the log location of the transport engine."""
        rayvision_log_path = os.environ.get(TRANSFER_LOG, "")
        if bool(transfer_log_path) and os.path.exists(transfer_log_path):
            transfer_path = transfer_log_path
            if rayvision_log_path != transfer_log_path:
                os.environ.update({TRANSFER_LOG: transfer_path})
                subprocess.Popen('setx %s "%s" /m' % (TRANSFER_LOG, transfer_path), shell=True)
        elif os.path.exists(rayvision_log_path):
            transfer_path = rayvision_log_path
        else:
            if self.api.user_info['local_os'] == "windows":
                transfer_path = os.path.join(os.environ[WINDOWS_LOCAL_ENV], RENDERFARM_SDK)
            else:
                transfer_path = os.path.join(os.environ[LINUX_LOCAL_ENV], RENDERFARM_SDK)

            os.environ.update({TRANSFER_LOG: transfer_path})
            subprocess.Popen('setx %s "%s" /m' % (TRANSFER_LOG, transfer_path), shell=True)

        return transfer_path

    def _check_and_mk(self, custom_db_path):
        """Check the path to the DB data file generated by the upload asset."""
        rayvision_db_env = os.environ.get(RAYVISION_DB, "")
        if bool(custom_db_path) and os.path.exists(custom_db_path):
            db_path = custom_db_path
        elif os.path.exists(rayvision_db_env):
            db_path = rayvision_db_env
        else:
            if self.api.user_info['local_os'] == "windows":
                db_path = os.path.join(os.environ[WINDOWS_LOCAL_ENV], RENDERFARM_SDK)
            else:
                db_path = os.path.join(os.environ[LINUX_LOCAL_ENV], RENDERFARM_SDK)

        return db_path

    def create_db_ini(self, upload_json_path):
        """Create the database configuration file.

        Args:
            upload_json_path (str): Upload json path.

        Returns:
            str: Configuration file path.

        """
        db_type = self.database_config.get("type", "sqlite").strip().lower()
        try:
            # Prevent multi-thread lock-free problems
            if not os.path.exists(self.db_ini):
                os.makedirs(self.db_ini)
        except:
            pass
        time_temp = os.path.split(os.path.dirname(upload_json_path))[-1]
        db_path = os.path.join(self._db, "%s.db" % time_temp)
        config_ini = configparser.ConfigParser()
        config_ini['database'] = {
            "on": self.database_config.get("on", "true"),
            "platform_id": self.trans.platform,
            "type": db_type
        }
        config_ini['redis'] = {
            "host": self.redis_config.get("host", "127.0.0.1"),
            "port": self.redis_config.get("port", 6379),
            "password": self.redis_config.get("password", ""),
            "table_index": self.redis_config.get("table_index", ""),
            "timeout": self.redis_config.get("timeout", 5000)
        }
        config_ini['sqlite'] = {
            "db_path": db_path,
            "temporary": self.sqlite_config.get("temporary", "false")
        }
        if db_type == "redis":
            db_ini_path = os.path.join(self.db_ini, "db_redis.ini")
        elif db_type == "sqlite":
            db_ini_path = os.path.join(self.db_ini, "%s.ini" % time_temp)
        else:
            error_data_msg = "{} is not a supported database, only support 'redis' or 'sqlite'".format(db_type)
            raise UnsupportedDatabaseError(error_data_msg)

        with open(db_ini_path, 'w') as configfile:
            config_ini.write(configfile)
        return db_ini_path

    def upload(self, task_id, task_json_path, tips_json_path, asset_json_path,
               upload_json_path, max_speed=None, transmit_type="upload_json",
               engine_type="aspera", server_ip=None, server_port=None,
               network_mode=0, is_record=False, redis_flag=None, redis_obj=None):
        """Run the cmd command to upload the configuration file.

        Args:
            task_id (str, optional): Task id.
            task_json_path (str, optional): task.json file absolute path.
            tips_json_path (str, optional): tips.json file absolute path.
            asset_json_path (str, optional): asset.json file absolute path.
            upload_json_path (str, optional): upload.json file absolute path.
            max_speed (str): Maximum transmission speed, default value
                is 1048576 KB/S.
            transmit_type (str): transmit type:
                1. upload_json: upload from json file,in this type, next remote will not used.
                2. upload_list: upload from file list.
            engine_type (str, optional): set engine type, support "aspera" and "raysync", Default "aspera".
            server_ip (str, optional): transmit server host,
                if not set, it is obtained from the default transport profile.
            server_port (str, optional): transmit server port,
                if not set, it is obtained from the default transport profile.
            network_mode (int): network mode: 0: auto selected, default;
                                               1: tcp;
                                               2: udp;
            is_record (bool): Whether to save upload records. default False.
            redis_flag (str): Save uploaded Redis database tag name.
            redis_obj (object): redis database object.

        Returns:
            bool: True is success, False is failure.

        """
        config_file_list = [
            task_json_path,
            tips_json_path,
            asset_json_path,
            upload_json_path
        ]
        result_config = self.upload_config(task_id, config_file_list, max_speed,
                                           engine_type=engine_type, server_ip=server_ip, server_port=server_port,
                                           network_mode=network_mode)
        if not result_config:
            return False
        result_asset = self.upload_asset(upload_json_path, max_speed, transmit_type,
                                         engine_type=engine_type, server_ip=server_ip, server_port=server_port,
                                         network_mode=network_mode, is_record=is_record, redis_flag=redis_flag,
                                         redis_obj=redis_obj)
        if not result_asset:
            return False
        return True

    def upload_config(self, task_id, config_file_list, max_speed=None,
                      engine_type="aspera", server_ip=None, server_port=None,
                      network_mode=0):
        """Run the cmd command to upload configuration profiles.

        Args:
            task_id (str): Task id.
            config_file_list (list): Configuration file path list.
            max_speed (str): Maximum transmission speed, default value
                is 1048576 KB/S.
            engine_type (str, optional): set engine type, support "aspera" and "raysync", Default "aspera".
            server_ip (str, optional): transmit server host,
                if not set, it is obtained from the default transport profile.
            server_port (str, optional): transmit server port,
                if not set, it is obtained from the default transport profile.
            network_mode (int): network mode: 0: auto selected, default;
                                               1: tcp;
                                               2: udp;

        Returns:
            bool: True is success, False is failure.

        """
        transmit_type = "upload_path"
        max_speed = max_speed if max_speed is not None else "1048576"

        for config_path in config_file_list:
            local_path = str2unicode(config_path)

            config_basename = os.path.basename(config_path)
            server_path = '/{0}/cfg/{1}'.format(task_id, config_basename)
            server_path = str2unicode(server_path)

            if not os.path.exists(local_path):
                self.logger.info('%s is not exists.', local_path)
                continue
            cmd_params = [transmit_type, local_path, server_path, max_speed,
                          'false', 'config_bid']
            cmd = self.trans.create_cmd(cmd_params, engine_type=engine_type, server_ip=server_ip,
                                        server_port=server_port, network_mode=network_mode)

            times = 0
            while True:
                result = run_cmd(cmd, flag=True, logger=self.logger)
                if result:
                    if times == 9:
                        raise RayvisionError(20004, "%s upload failed" %
                                             config_path)
                    times += 1
                else:
                    break
        return True

    @upload_retry
    def upload_asset(self, upload_json_path, max_speed=None, is_db=True,
                     engine_type="aspera", server_ip=None, server_port=None,
                     transmit_type="upload_json", network_mode=0, redis_flag=None,
                     is_record=False, redis_obj=None):
        """Run the cmd command to upload asset files.

        Args:
            upload_json_path (str): Path to the upload.json file.
            max_speed (str): Maximum transmission speed, default value
                is 1048576 KB/S.
            is_db (bool): Whether to produce local database record upload file.
            engine_type (str): Transport engine type, supports "aspera" and "raysync".
            server_ip (str): Transport server IP.
            server_port (str): Transport server port.
            transmit_type (str): transmit type:
                1. upload_json: upload from json file,in this type, next remote will not used.
                2. upload_list: upload from file list.
            network_mode (int): network mode: 0: auto selected, default;
                                               1: tcp;
                                               2: udp;
            is_record (bool): Whether to save upload records. default False.
            redis_flag (str): Save uploaded Redis database tag name.
            redis_obj (object): redis database object.

        Returns:
            bool: True is success, False is failure.

        """
        max_speed = max_speed if max_speed is not None else "1048576"
        cmd_params = [transmit_type, upload_json_path, '/', max_speed,
                      'false', 'input_bid']
        if is_db:
            db_ini_path = self.create_db_ini(upload_json_path)
        else:
            db_ini_path = None
        main_input_bid, main_user_id = get_share_info(self.api)
        cmd = self.trans.create_cmd(cmd_params, db_ini_path, engine_type, server_ip, server_port,
                                    main_user_id=main_user_id, main_input_bid=main_input_bid,
                                    network_mode=network_mode)

        return run_cmd(cmd, flag=True, logger=self.logger, is_record=is_record, redis_flag=redis_flag, redis_obj=redis_obj)

    def load_db_config(self, db_config_path=None):
        if not bool(db_config_path) or not os.path.exists(db_config_path):
            db_config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "db_config.ini"))
        conf = read_ini_config(db_config_path)
        on = conf.get("DATABASE_CONFIG", "on")
        type = conf.get("DATABASE_CONFIG", "type")
        db_path = conf.get("DATABASE_CONFIG", "db_path")
        host = conf.get("REDIS", "host")
        port = conf.get("REDIS", "port")
        password = conf.get("REDIS", "password")
        table_index = conf.get("REDIS", "table_index")
        timeout = conf.get("REDIS", "timeout")
        temporary = conf.get("SQLITE", "temporary")
        transfer_log_path = conf.get("TRANSFER_LOG_PATH", "transfer_log_path")

        database_config = {
            "on": on,
            "type": type,
            "db_path": db_path
        }
        redis_config = {
            "host": host,
            "port": int(port),
            "password": password,
            "table_index": table_index,
            "timeout": timeout
        }
        sqlite_config = {
            "temporary": temporary
        }

        return transfer_log_path, redis_config, sqlite_config, database_config

    def thread_pool_upload(self, upload_pool, pool_size=10, **kwargs):
        """Thread pool upload.

        Args:
            upload_pool (list or tuple): store a list or ancestor of uploaded files.
            pool_size (int): thread pool size, default is 10 threads.

        """
        kwargs.pop("is_db")
        pool = ThreadPoolExecutor(pool_size)
        for i in range(len(upload_pool)):
            pool.submit(self.upload_asset, upload_json_path=upload_pool[i], is_db=False, **kwargs)
        pool.shutdown(wait=True)
