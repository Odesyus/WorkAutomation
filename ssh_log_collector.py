"""
=============================================================================
SSH LOG COLLECTOR (TEMPLATE)
=============================================================================
Bu script, SecureCRT arayüzüne ihtiyaç duymadan uzak Linux/Unix sunucularına 
SSH ile bağlanıp logları çekmek veya SFTP ile doğrudan indirmek için hazırlanmıştır.

Gereksinim:
    pip install paramiko
=============================================================================
"""

import os
from datetime import datetime
import paramiko
import config


class SSHLogCollector:
    def __init__(self, host, username, password, port=22, timeout=15):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.client = None

    def connect(self):
        """Sunucuya SSH bağlantısı kurar."""
        try:
            print(f"[*] {self.host}:{self.port} sunucusuna bağlanılıyor...")
            self.client = paramiko.SSHClient()
            # Bilinmeyen host key'lerini otomatik kabul et (SecureCRT gibi)
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout
            )
            print("[+] Bağlantı başarılı.")
            return True
        except paramiko.AuthenticationException:
            print("[!] Kimlik doğrulama hatası! Kullanıcı adı veya şifre yanlış.")
        except Exception as e:
            print(f"[!] Bağlantı hatası: {str(e)}")
        return False

    def run_command(self, command):
        """Uzak sunucuda tek bir komut çalıştırıp çıktısını döndürür."""
        if not self.client:
            print("[!] Önce sunucuya bağlanmalısınız.")
            return None

        try:
            print(f"[*] Komut çalıştırılıyor: {command}")
            stdin, stdout, stderr = self.client.exec_command(command)
            
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')

            if error and not output:
                print(f"[!] Hata çıktısı alındı:\n{error}")
                return error
            return output
        except Exception as e:
            print(f"[!] Komut yürütülürken hata: {str(e)}")
            return None

    def save_log_to_file(self, content, local_dir="logs", filename_prefix="server_log"):
        """Çekilen log içeriğini yerel diske tarih-saat etiketiyle kaydeder."""
        if not content:
            print("[!] Kaydedilecek log içeriği bulunamadı.")
            return None

        os.makedirs(local_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.log"
        file_path = os.path.join(local_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[+] Log başarıyla kaydedildi: {file_path}")
        return file_path

    def download_file_sftp(self, remote_file_path, local_dir="logs"):
        """
        Büyük log dosyalarını terminalden basmak yerine 
        SFTP ile doğrudan bilgisayarınıza indirir (Çok daha hızlıdır).
        """
        if not self.client:
            print("[!] Önce sunucuya bağlanmalısınız.")
            return False

        try:
            os.makedirs(local_dir, exist_ok=True)
            local_filename = os.path.basename(remote_file_path)
            # Başına tarih ekleyerek çakışmayı önleyelim
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            local_file_path = os.path.join(local_dir, f"{timestamp}_{local_filename}")

            print(f"[*] Dosya indiriliyor: {remote_file_path} -> {local_file_path}")
            sftp = self.client.open_sftp()
            sftp.get(remote_file_path, local_file_path)
            sftp.close()

            print(f"[+] Dosya başarıyla indirildi: {local_file_path}")
            return local_file_path
        except Exception as e:
            print(f"[!] SFTP indirme hatası: {str(e)}")
            return None

    def close(self):
        """SSH bağlantısını kapatır."""
        if self.client:
            self.client.close()
            print("[*] Bağlantı kapatıldı.")


# =============================================================================
# KULLANIM ÖRNEĞİ / TEST ALANI
# =============================================================================
if __name__ == "__main__":
    # 1. Ortak Sunucu Bilgileri config.py modülünden alınır
    collector = SSHLogCollector(
        host=config.SSH_CONFIG["host"],
        username=config.SSH_CONFIG["username"],
        password=config.SSH_CONFIG["password"],
        port=config.SSH_CONFIG["port"],
        timeout=config.SSH_CONFIG["timeout"]
    )

    if collector.connect():
        # --- YÖNTEM A: Komut Çıktısı Olarak Log Çekme (grep / tail / cat) ---
        # Örnek: Son 200 satırı çekmek veya belli bir MSISDN filtrelemek:
        cmd = "cd /opt/simulator/entitlement-client-23.0.0.15-20230227151044678 && tail prop_pstest.properties -n 2000"
        # cmd = "grep -i '5051234567' /argela/deploy/LOGS/app.log | tail -n 100"
        
        log_content = collector.run_command(cmd)
        if log_content:
            # Yerel 'logs' klasörüne kaydet
            print(log_content)
            #collector.save_log_to_file(log_content, local_dir="downloaded_logs", filename_prefix="argela_log")

        # --- YÖNTEM B: Büyük Bir Dosyayı SFTP ile Doğrudan İndirme ---
        # remote_log_path = "/argela/deploy/LOGS/app.log"
        # collector.download_file_sftp(remote_log_path, local_dir="downloaded_logs")

        # İşlem bitince bağlantıyı kapat
        collector.close()
