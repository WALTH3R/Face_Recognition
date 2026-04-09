import os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


class SecurityManager:
    SALT_LENGTH = 16
    NONCE_LENGTH = 12
    TAG_LENGTH = 16
    KEY_LENGTH = 32
    ITERATIONS = 600000
    
    def __init__(self, password, salt=None, encodings_dir="encodings"):
        if not isinstance(password, str) or not password:
            raise ValueError("Password must be a non-empty string")
        
        self.password = password.encode()
        self.salt = salt if salt is not None else os.urandom(self.SALT_LENGTH)
        self.encodings_dir = Path(encodings_dir)
        self.key = self._derive_key()

    def _derive_key(self):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH,
            salt=self.salt,
            iterations=self.ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(self.password)

    def encrypt_data(self, data, student_name):
        if not isinstance(data, bytes):
            raise ValueError("Data must be bytes")
        if not isinstance(student_name, str) or not student_name.strip():
            raise ValueError("Student name must be a non-empty string")
        
        student_name = "".join(c for c in student_name if c.isalnum() or c in "-_")
        if not student_name:
            raise ValueError("Student name contains no valid characters")
        
        nonce = os.urandom(self.NONCE_LENGTH)
        
        try:
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(nonce),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(data) + encryptor.finalize()
            tag = encryptor.tag
            
            payload = self.salt + nonce + tag + encrypted_data
            
            self.encodings_dir.mkdir(parents=True, exist_ok=True)
            file_path = self.encodings_dir / f"{student_name}.enc"
            
            with open(file_path, 'wb') as f:
                f.write(payload)
            
            return file_path
            
        except Exception as e:
            raise OSError(f"Failed to encrypt data for {student_name}: {str(e)}")

    def decrypt_data(self, student_name):
        student_name = "".join(c for c in student_name if c.isalnum() or c in "-_")
        
        file_path = self.encodings_dir / f"{student_name}.enc"
        
        if not file_path.exists():
            raise FileNotFoundError(f"No encoding found for {student_name}")
        
        try:
            with open(file_path, 'rb') as f:
                payload = f.read()
            
            min_size = self.SALT_LENGTH + self.NONCE_LENGTH + self.TAG_LENGTH
            if len(payload) < min_size:
                raise ValueError("Invalid encrypted file format")
            
            salt = payload[:self.SALT_LENGTH]
            nonce = payload[self.SALT_LENGTH:self.SALT_LENGTH + self.NONCE_LENGTH]
            tag = payload[self.SALT_LENGTH + self.NONCE_LENGTH:self.SALT_LENGTH + self.NONCE_LENGTH + self.TAG_LENGTH]
            encrypted_data = payload[self.SALT_LENGTH + self.NONCE_LENGTH + self.TAG_LENGTH:]
            
            temp_manager = SecurityManager(
                self.password.decode(),
                salt=salt,
                encodings_dir=str(self.encodings_dir)
            )
            
            cipher = Cipher(
                algorithms.AES(temp_manager.key),
                modes.GCM(nonce, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
            
            return decrypted_data
            
        except FileNotFoundError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to decrypt data for {student_name}: {str(e)}")

    def delete_encoding(self, student_name):
        student_name = "".join(c for c in student_name if c.isalnum() or c in "-_")
        file_path = self.encodings_dir / f"{student_name}.enc"
        
        if not file_path.exists():
            raise FileNotFoundError(f"No encoding found for {student_name}")
        
        file_size = file_path.stat().st_size
        with open(file_path, 'wb') as f:
            f.write(os.urandom(file_size))
        
        file_path.unlink()

