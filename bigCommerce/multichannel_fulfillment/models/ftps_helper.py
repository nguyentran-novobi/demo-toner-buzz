import os
import ftplib


class FTPSHelper:
    def __init__(self, host: str, username: str, password: str, base_path: str):
        self.host = host
        self.username = username
        self.password = password
        self.base_path = base_path or ''
        self.ftps = None

    def __enter__(self):
        self.ftps = ftplib.FTP_TLS(self.host)
        self.ftps.set_pasv(True)
        self.ftps.connect(port=21, timeout=80)
        self.ftps.login(self.username, self.password)
        self.ftps.prot_p()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.ftps:
            try:
                self.ftps.quit()
            except AttributeError:
                pass
            finally:
                self.ftps = None

    def send_file(self, path: str, file, name: str):
        try:
            full_path = os.path.join('/', self.base_path, path)
            self.ftps.cwd(full_path)
            self.ftps.storbinary(f'STOR {name}', file)
        except AttributeError:
            pass
