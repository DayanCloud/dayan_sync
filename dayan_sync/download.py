# coding=utf-8
"""Download models.

Including download, automatic download (the task is fully rendered,
one frame is downloaded after downloading one frame), download so
the un-downloaded task is recorded (the task is rendered).

"""

import os
# Import built-in modules
import time
import logging

from dayan_sync.manage import RayvisionManageTask
# Import local modules
from dayan_sync.transfer import RayvisionTransfer
from dayan_sync.exception import DownloadFailed
from dayan_sync.utils import create_transfer_params
from dayan_sync.utils import run_cmd
from dayan_sync.utils import str2unicode
from rayvision_log import init_logger
from dayan_sync.constants import PACKAGE_NAME


class RayvisionDownload(object):
    """Downloader.

    Download all the passed tasks by calling the cmd command.

    """

    def __init__(self, api,
                 transports_json="",
                 transmitter_exe="",
                 automatic_line=False,
                 internet_provider="",
                 logger=None,
                 log_folder=None,
                 log_name=None,
                 log_level="DEBUG",
                 ):
        """Initialize instance.

        Args:
            api (object): rayvision api object.
            transports_json (string): Customize the absolute path of the transfer configuration file.
            transmitter_exe (string): Customize the absolute path of the transfer execution file.
            automatic_line (bool): Whether to automatically obtain the transmission line, the default is "False"
            internet_provider (string): Network provider.
            logger (object): Customize log object.
            log_folder (string): Customize the absolute path of the folder where logs are stored.
            log_name (string): Custom log file name, the system user name will be searched by default.
            log_level (string):  Set log level, example: "DEBUG","INFO","WARNING","ERROR"
        """
        params = create_transfer_params(api)
        params["transports_json"] = transports_json
        params["transmitter_exe"] = transmitter_exe
        params["automatic_line"] = automatic_line
        params["internet_provider"] = internet_provider
        self.api = api
        self.trans = RayvisionTransfer(api, **params)
        self.manage_task = self.trans.manage_task or RayvisionManageTask(api.query)
        self.logger = logger
        if not self.logger:
            init_logger(PACKAGE_NAME, log_folder, log_name)
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(level=log_level.upper())

    def _download_log(self, task_id_list, local_path):
        """Download log Settings.

        Args:
            task_id_list (list): List of tasks ids that need to be downloaded.

        """
        self.logger.info('INPUT:')
        self.logger.info('=' * 20)
        self.logger.info('task_id_list: %s', task_id_list)
        self.logger.info('local_path: %s', local_path)
        self.logger.info('=' * 20)

    def _check_local_path(self, local_path):
        """Check the download path.

        Args:
            local_path (str):  Local path to download.

        Returns:
            str

        """
        if not local_path:
            if self.api.user_info['local_os'] == "windows":
                local_path = os.path.join(os.environ["USERPROFILE"],
                                          "renderfarm_sdk")
            else:
                local_path = os.path.join(os.environ["HOME"], "renderfarm_sdk")
        return local_path

    @staticmethod
    def check_params(task_id_list, custom_server_output_path):
        """Check the parameters.
        
        Task_id_list and custom_server_output_path must have one.
        """
        if not task_id_list and not custom_server_output_path:
            raise Exception("One of the task_id_list and custom_server_output_path"
                            " must exist")

    def download(self, task_id_list=None,
                 max_speed=None, print_log=True,
                 download_filename_format="true",
                 local_path=None, server_path=None,
                 engine_type="aspera", server_ip=None, server_port=None,
                 network_mode=0):
        """Download and update the undownloaded record.

        Args:
            task_id_list (list of int): List of tasks ids that need to be
                downloaded.
            max_speed (str, optional): Download speed limit,
                The unit of ``max_speed`` is KB/S,default value is 1048576
                KB/S, means 1 GB/S.
            print_log (bool, optional): Print log, True: print, False: not
                print.
            download_filename_format: File download local save style,
                "true": tape task ID and scene name,
                "false" : download directly without doing processing.
            local_path (str): Download file locally save path,
                default Window system is "USERPROFILE" environment variable address splicing "renderfarm_sdk",
                Linux system is "HOME" environment variable address splicing "renderfarm_sdk",
            server_path (str or list): The user customizes the file structure to be downloaded from
                the output server, and all file structures are downloaded by default,
                example: "18164087_test/l_layer".
            engine_type (str, optional): set engine type, support "aspera" and "raysync", Default "aspera".
            server_ip (str, optional): transmit server host,
                if not set, it is obtained from the default transport profile.
            server_port (str, optional): transmit server port,
                if not set, it is obtained from the default transport profile.
            network_mode (int): network mode: 0: auto selected, default;
                                               1: tcp;
                                               2: udp;

        Returns:
            bool: True is success.

        """
        self.check_params(task_id_list, server_path)
        local_path = self._check_local_path(local_path)
        self.logger.info("[Rayvision_sync start download .....]")
        self._download_log(task_id_list, local_path)

        self._run_download(task_id_list, local_path, max_speed, print_log,
                           download_filename_format, server_path,
                           engine_type=engine_type, server_ip=server_ip, server_port=server_port,
                           network_mode=network_mode)
        self.logger.info("[Rayvision_sync end download.....]")
        return True

    def download_block(self, task_id_list=None,
                       max_speed=None, print_log=True, download_filename_format="true",
                       sleep_time=10, local_path=None, server_path=None,
                       engine_type="aspera", server_ip=None, server_port=None,
                       network_mode=0, download_type=None):
        self.check_params(task_id_list, server_path)
        local_path = self._check_local_path(local_path)
        self.logger.info("[Rayvision_sync start download block.....]")
        self._download_log(task_id_list, local_path)

        while True:
            if task_id_list:
                time.sleep(float(sleep_time))
                for task_id in task_id_list:
                    task_status_list = self.manage_task.get_task_status(task_id_list)
                    sub_task_status_list = (self.manage_task.get_sub_status(task_status_list))

                    assert '45' not in sub_task_status_list, "????????????!"

                    if '25' in sub_task_status_list:
                        download_flag = True
                        try:
                            self._run_cc_download([task_id], local_path, max_speed,
                                               print_log, download_filename_format,
                                               engine_type=engine_type, server_ip=server_ip, server_port=server_port,
                                               network_mode=network_mode, download_type=download_type)
                        except DownloadFailed:
                            download_flag = False
                        if download_flag is True:
                            task_id_list.remove(task_id)
            else:
                break
        self.logger.info("[Rayvision_sync end download.....]")
        return True

    def auto_download(self, task_id_list=None, max_speed=None,
                      print_log=False, sleep_time=10,
                      download_filename_format="true",
                      local_path=None,
                      engine_type="aspera", server_ip=None, server_port=None,
                      network_mode=0):
        """Automatic download (complete one frame download).

        Wait for all downloads to update undownloaded records.

        Args:
            task_id_list (list of int): List of tasks ids that need to be
                downloaded.
            max_speed (str, optional): Download speed limit,
                The unit of 'max_speed' is KB/S,default value is 1048576 KB/S,
                means 1 GB/S.
            print_log (bool, optional): Print log, True: print, False: not
                print.
            sleep_time (int, optional): Sleep time between download,
                unit is second.
            download_filename_format: File download local save style,
                "true": tape task ID and scene name,
                "false" : download directly without doing processing.
            local_path (str): Download file locally save path,
                default Window system is "USERPROFILE" environment variable address splicing "renderfarm_sdk",
                Linux system is "HOME" environment variable address splicing "renderfarm_sdk".
            engine_type (str, optional): set engine type, support "aspera" and "raysync", Default "aspera".
            server_ip (str, optional): transmit server host,
                if not set, it is obtained from the default transport profile.
            server_port (str, optional): transmit server port,
                if not set, it is obtained from the default transport profile.
            network_mode (int): network mode??? 0: auto selected, default,
                                               1:tcp
                                               2:udp
        Returns:
            bool: True is success.

        """
        local_path = self._check_local_path(local_path)
        self.logger.info("[Rayvision_sync start auto_download.....]")
        self._download_log(task_id_list, local_path)

        self._auto_download_tool(task_id_list, sleep_time,
                                 max_speed, print_log, local_path,
                                 download_filename_format,
                                 engine_type=engine_type, server_ip=server_ip, server_port=server_port,
                                 network_mode=network_mode)
        self.logger.info("[Rayvision_sync end auto_download.....]")
        return True

    def _auto_download_tool(self, task_id_list, sleep_time,
                            max_speed, print_log, local_path,
                            download_filename_format="true",
                            engine_type=None, server_ip=None, server_port=None,
                            network_mode=0):
        """Automatic download (complete one frame download).

        Args:
            task_id_list(list of int): List of tasks ids that need to be
                downloaded.
            sleep_time(int):  Sleep time between download.
            max_speed(str): Download speed limit.
            print_log(bool): Print log, True: print, False: not print.
            download_filename_format(str): File download local save style,
                "true": tape task ID and scene name,
                "false" : download directly without doing processing.

        """
        download_failed_list = list()
        while True:
            if task_id_list:
                time.sleep(float(sleep_time))
                task_id_list_copy = task_id_list.copy()
                for task_id in task_id_list:
                    download_flag = True
                    is_task_end = self.manage_task.is_task_end(task_id)
                    try:
                        self._run_download([task_id], local_path, max_speed,
                                           print_log, download_filename_format,
                                           engine_type=engine_type, server_ip=server_ip, server_port=server_port,
                                           network_mode=network_mode)
                    except DownloadFailed:
                        download_flag = False

                    if is_task_end is True and download_flag is False:
                        download_failed_list.append(task_id)

                    if is_task_end is True:
                        self.logger.info('The tasks end: %s', task_id)
                        task_id_list_copy.remove(task_id)
                task_id_list = task_id_list_copy.copy()
            else:
                break
        if download_failed_list:
            raise DownloadFailed('Finally tasks download failed: %s' % str(download_failed_list))

    def auto_download_after_task_completed(self, task_id_list=None,
                                           max_speed=None, print_log=True,
                                           sleep_time=10,
                                           download_filename_format="true",
                                           local_path=None,
                                           engine_type="aspera", server_ip=None, server_port=None,
                                           network_mode=0):
        """Auto download after the tasks render completed.

        Args:
            task_id_list(list of int): List of tasks ids that need to be
                downloaded.
            max_speed(str, optional): Download speed limit,
                The unit of 'max_speed' is KB/S,default value is 1048576 KB/S,
                means 1 GB/S.
            print_log(bool, optional): Print log, True: print, False: not
                print.
            sleep_time(int, optional): Sleep time between download,
                unit is second.
            download_filename_format: File download local save style,
                "true": tape task ID and scene name,
                "false" : download directly without doing processing.
            local_path (str): Download file locally save path,
                default Window system is "USERPROFILE" environment variable address splicing "renderfarm_sdk",
                Linux system is "HOME" environment variable address splicing "renderfarm_sdk".
            engine_type (str, optional): set engine type, support "aspera" and "raysync", Default "aspera".
            server_ip (str, optional): transmit server host,
                if not set, it is obtained from the default transport profile.
            server_port (str, optional): transmit server port,
                if not set, it is obtained from the default transport profile.
            network_mode (int): network mode??? 0: auto selected, default;
                                               1: tcp;
                                               2: udp;

        Returns:
            bool: True is success.

        """
        local_path = self._check_local_path(local_path)
        self.logger.info("[Rayvision_sync start"
                         "auto_download_after_task_completed .....]")
        self._download_log(task_id_list, local_path)

        while True:
            if task_id_list:
                time.sleep(float(sleep_time))
                for task_id in task_id_list:
                    is_task_end = self.manage_task.is_task_end(task_id)

                    if is_task_end is True:
                        time.sleep(float(5))
                        self.logger.info('The tasks end: %s', task_id)
                        self._run_download([task_id], local_path,
                                           max_speed, print_log,
                                           download_filename_format,
                                           engine_type=engine_type, server_ip=server_ip, server_port=server_port,
                                           network_mode=network_mode)
                        task_id_list.remove(task_id)
            else:
                break
        self.logger.info("[Rayvision_sync end -- "
                         "auto_download_after_task_completed......]")

        return True

    def auto_download_cc_after_task_completed(self, task_id_list=None,
                                           max_speed=None, print_log=True,
                                           sleep_time=10,
                                           download_filename_format="true",
                                           local_path=None,
                                           engine_type="aspera", server_ip=None, server_port=None,
                                           network_mode=0, download_type=None):
        """Auto download after the tasks render completed.

        Args:
            task_id_list(list of int): List of tasks ids that need to be
                downloaded.
            max_speed(str, optional): Download speed limit,
                The unit of 'max_speed' is KB/S,default value is 1048576 KB/S,
                means 1 GB/S.
            print_log(bool, optional): Print log, True: print, False: not
                print.
            sleep_time(int, optional): Sleep time between download,
                unit is second.
            download_filename_format: File download local save style,
                "true": tape task ID and scene name,
                "false" : download directly without doing processing.
            local_path (str): Download file locally save path,
                default Window system is "USERPROFILE" environment variable address splicing "renderfarm_sdk",
                Linux system is "HOME" environment variable address splicing "renderfarm_sdk".
            engine_type (str, optional): set engine type, support "aspera" and "raysync", Default "aspera".
            server_ip (str, optional): transmit server host,
                if not set, it is obtained from the default transport profile.
            server_port (str, optional): transmit server port,
                if not set, it is obtained from the default transport profile.
            network_mode (int): network mode??? 0: auto selected, default;
                                               1: tcp;
                                               2: udp;

        Returns:
            bool: True is success.

        """
        local_path = self._check_local_path(local_path)
        self.logger.info("[Rayvision_sync start"
                         "auto_download_after_task_completed .....]")
        self._download_log(task_id_list, local_path)

        while True:
            sub_task_status_list = []
            if task_id_list:
                time.sleep(float(sleep_time))
                for task_id in task_id_list:
                    task_status_list = self.manage_task.get_task_status(task_id_list)
                    render_type_list = self.manage_task.get_render_type(task_status_list)
                    sub_task_status_list = (self.manage_task.get_sub_status(task_status_list))

                    assert '45' not in sub_task_status_list, "????????????!"

                    is_done = (len(set(sub_task_status_list)) == 1) or (len(set(sub_task_status_list)) == 2 and (['25', '30'] == sorted(set(sub_task_status_list))))

                    if 'Rebuild' in render_type_list and len(render_type_list) > 2 and is_done:
                        time.sleep(float(5))
                        self.logger.info('The tasks end: %s', task_id)
                        self._run_cc_download([task_id], local_path,
                                           max_speed, print_log,
                                           download_filename_format,
                                           engine_type=engine_type, server_ip=server_ip, server_port=server_port,
                                           network_mode=network_mode, download_type=download_type)
                        task_id_list.remove(task_id)
            else:
                break
            if '30' in sub_task_status_list:
                self.logger.info("???????????????????????????")

        self.logger.info("[Rayvision_sync end -- "
                         "auto_download_after_task_completed......]")

        return True

    def _run_cc_download(self, task_id_list, local_path, max_speed=None,
                      print_log=True, download_filename_format="true",
                      server_path=None, engine_type="aspera", server_ip=None,
                      server_port=None,
                      network_mode=0, download_type=None):
        """Execute the cmd command for multitasking download.

        Args:
            task_id_list (list of int): Task id list.
            local_path (str): Download to local path.
            max_speed (str): Maximum transmission speed, default value
                is 1048576 KB/S.
            print_log (bool): Print log, True: print, False: not print.
            download_filename_format: File download local save style,
                "true": tape task ID and scene name,
                "false" : download directly without doing processing.
            server_path (str / list): The user customizes the file structure to be downloaded from
                the output server, and all file structures are downloaded by default,
                example: "18164087_test/l_layer".
            engine_type (str, optional): set engine type, support "aspera" and "raysync", Default "aspera".
            server_ip (str, optional): transmit server host,
                if not set, it is obtained from the default transport profile.
            server_port (str, optional): transmit server port,
                if not set, it is obtained from the default transport profile.
            network_mode (int): network mode??? 0: auto selected, default;
                                               1: tcp;
                                               2: udp;

        """
        transmit_type = 'download_path'
        local_path = str2unicode(local_path)
        # The unit of 'max_speed' is KB/S, default value is 1048576 KB/S,
        #  means 1 GB/S.
        max_speed = max_speed if max_speed is not None else "1048576"

        if download_type is 'block':
            for task_id in task_id_list:
                output = str(task_id) + r'\at_result'
                cmd_params = [transmit_type, local_path, output,
                              max_speed, download_filename_format, 'output_bid']
                self.create_cmd(cmd_params, engine_type=engine_type,
                                server_ip=server_ip, server_port=server_port,
                                network_mode=network_mode, print_log=print_log, output=output)
        elif download_type is 'render':
            for task_id in task_id_list:
                output = str(task_id) + r'\render_result'
                cmd_params = [transmit_type, local_path, output,
                              max_speed, download_filename_format, 'output_bid']
                self.create_cmd(cmd_params, engine_type=engine_type,
                                server_ip=server_ip, server_port=server_port,
                                network_mode=network_mode, print_log=print_log, output=output)

    def create_cmd(self, cmd_params, engine_type="raysync",
                   server_ip=None, server_port=None,
                   network_mode=0, print_log=True, output=''):
        cmd = self.trans.create_cmd(cmd_params, engine_type=engine_type,
                                    server_ip=server_ip, server_port=server_port,
                                    network_mode=network_mode)

        tranfer_code = run_cmd(cmd, print_log=print_log, logger=self.logger)
        if tranfer_code != 0:
            raise DownloadFailed('%s Download failed' % output)

    def _run_download(self, task_id_list, local_path, max_speed=None,
                      print_log=True, download_filename_format="true",
                      server_path=None, engine_type="aspera", server_ip=None, server_port=None,
                      network_mode=0):
        """Execute the cmd command for multitasking download.

        Args:
            task_id_list (list of int): Task id list.
            local_path (str): Download to local path.
            max_speed (str): Maximum transmission speed, default value
                is 1048576 KB/S.
            print_log (bool): Print log, True: print, False: not print.
            download_filename_format: File download local save style,
                "true": tape task ID and scene name,
                "false" : download directly without doing processing.
            server_path (str / list): The user customizes the file structure to be downloaded from
                the output server, and all file structures are downloaded by default,
                example: "18164087_test/l_layer".
            engine_type (str, optional): set engine type, support "aspera" and "raysync", Default "aspera".
            server_ip (str, optional): transmit server host,
                if not set, it is obtained from the default transport profile.
            server_port (str, optional): transmit server port,
                if not set, it is obtained from the default transport profile.
            network_mode (int): network mode??? 0: auto selected, default;
                                               1: tcp;
                                               2: udp;

        """
        transmit_type = 'download_path'
        local_path = str2unicode(local_path)
        # The unit of 'max_speed' is KB/S, default value is 1048576 KB/S,
        #  means 1 GB/S.
        max_speed = max_speed if max_speed is not None else "1048576"

        if not server_path:
            task_status_list = self.manage_task.get_task_status(task_id_list)
            output_file_names = (self.manage_task.
                                 output_file_names(task_status_list))
        else:
            if isinstance(server_path, str):
                output_file_names = [server_path]
            elif isinstance(server_path, list):
                isinstance(server_path, list)
                output_file_names = server_path
            else:
                raise Exception("custom_server_output_path must a list or str.")

        for output_file_name in output_file_names:
            cmd_params = [transmit_type, local_path, output_file_name,
                          max_speed, download_filename_format, 'output_bid']

            cmd = self.trans.create_cmd(cmd_params, engine_type=engine_type,
                                        server_ip=server_ip, server_port=server_port,
                                        network_mode=network_mode)
            tranfer_code = run_cmd(cmd, print_log=print_log, logger=self.logger)
            if tranfer_code != 0:
                raise DownloadFailed('%s Download failed' % output_file_name)

