import os
import stat
import logging
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
import atexit

logger = logging.getLogger(__name__)


class SecurityManager:
    
    SALT_LENGTH = 16
    NONCE_LENGTH = 12
    TAG_LENGTH = 16
    KEY_LENGTH = 32
    
    SCRYPT_N = 2**14
    SCRYPT_R = 8
    SCRYPT_P = 1
    
    def __init__(self, password, salt=None, encodings_dir="encodings"):
        if not isinstance(password, str) or not password:
            raise ValueError("Password must be a non-empty string")
        
        self.password = password.encode()
        self.salt = salt if salt is not None else os.urandom(self.SALT_LENGTH)
        self.encodings_dir = Path(encodings_dir)
        self.key = self._derive_key()
        
        atexit.register(self._cleanup)

    def __del__(self):
        self._cleanup()

    def _cleanup(self):
        if hasattr(self, 'password') and self.password:
            self.password = b'\x00' * len(self.password)

    def _derive_key(self):
        try:
            kdf = Scrypt(
                algorithm=hashes.SHA256(),
                length=self.KEY_LENGTH,
                salt=self.salt,
                n=self.SCRYPT_N,
                r=self.SCRYPT_R,
                p=self.SCRYPT_P,
            )
            return kdf.derive(self.password)
        except Exception as e:
            logger.error(f"Key derivation failed: {str(e)}")
            raise RuntimeError(f"Failed to derive encryption key: {str(e)}")

    def _sanitize_student_name(self, student_name):
        if not isinstance(student_name, str) or not student_name.strip():
            raise ValueError("Student name must be a non-empty string")
        
        sanitized = "".join(c for c in student_name if c.isalnum() or c in "-_")
        if not sanitized:
            raise ValueError("Student name contains no valid characters")
        
        return sanitized

    def encrypt_data(self, data, student_name):
        if not isinstance(data, bytes):
            raise ValueError("Data must be bytes")
        
        student_name = self._sanitize_student_name(student_name)
        nonce = os.urandom(self.NONCE_LENGTH)
        
        try:
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(nonce),
            )
            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(data) + encryptor.finalize()
            tag = encryptor.tag
            
            payload = nonce + tag + encrypted_data
            
            self.encodings_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            file_path = self.encodings_dir / f"{student_name}.enc"
            
            with open(file_path, 'wb') as f:
                f.write(payload)
            
            os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
            
            logger.info(f"Successfully encrypted data for {student_name}")
            return file_path
            
        except Exception as e:
            logger.error(f"Encryption failed for {student_name}: {str(e)}")
            raise OSError(f"Failed to encrypt data for {student_name}: {str(e)}")

    def decrypt_data(self, student_name):
        student_name = self._sanitize_student_name(student_name)
        file_path = self.encodings_dir / f"{student_name}.enc"
        
        if not file_path.exists():
            raise FileNotFoundError(f"No encoding found for {student_name}")
        
        try:
            with open(file_path, 'rb') as f:
                payload = f.read()
            
            min_size = self.NONCE_LENGTH + self.TAG_LENGTH
            if len(payload) < min_size:
                raise ValueError("Invalid encrypted file format")
            
            nonce = payload[:self.NONCE_LENGTH]
            tag = payload[self.NONCE_LENGTH:self.NONCE_LENGTH + self.TAG_LENGTH]
            encrypted_data = payload[self.NONCE_LENGTH + self.TAG_LENGTH:]
            
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(nonce, tag),
            )
            decryptor = cipher.decryptor()
            decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
            
            logger.info(f"Successfully decrypted data for {student_name}")
            return decrypted_data
            
        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Decryption failed for {student_name}: {str(e)}")
            raise ValueError(f"Failed to decrypt data for {student_name}: {str(e)}")

    def delete_encoding(self, student_name):
        student_name = self._sanitize_student_name(student_name)
        file_path = self.encodings_dir / f"{student_name}.enc"
        
        if not file_path.exists():
            raise FileNotFoundError(f"No encoding found for {student_name}")
        
        try:
            file_size = file_path.stat().st_size
            
            for _ in range(3):
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())
            
            with open(file_path, 'wb') as f:
                f.write(b'\x00' * file_size)
                f.flush()
                os.fsync(f.fileno())
            
            file_path.unlink()
            logger.info(f"Successfully deleted encoding for {student_name}")
            
        except Exception as e:
            logger.error(f"Failed to delete encoding for {student_name}: {str(e)}")
            raise OSError(f"Failed to delete encoding for {student_name}: {str(e)}")

    def save_salt(self, salt_file):
        try:
            with open(salt_file, 'wb') as f:
                f.write(self.salt)
            os.chmod(salt_file, stat.S_IRUSR | stat.S_IWUSR)
            logger.info(f"Salt saved to {salt_file}")
        except Exception as e:
            logger.error(f"Failed to save salt: {str(e)}")
            raise OSError(f"Failed to save salt: {str(e)}")

    @staticmethod
    def load_salt(salt_file):
        try:
            with open(salt_file, 'rb') as f:
                salt = f.read()
            if len(salt) != 16:
                raise ValueError("Invalid salt length")
            return salt
        except Exception as e:
            logger.error(f"Failed to load salt: {str(e)}")
            raise
