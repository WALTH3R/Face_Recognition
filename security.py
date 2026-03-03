import os
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import json

class SecurityManager:
    def __init__(self, password):
        self.password = password.encode()
        self.salt = b'\x12\x34\x56\x78\x90\xab\xcd\xef' 
        self.key = self._derive_key()
        self.hashes_file = "encodings/hashes.json"
        
        if not os.path.exists("encodings"):
            os.makedirs("encodings")
        
        if not os.path.exists(self.hashes_file):
            with open(self.hashes_file, 'w') as f:
                json.dump({}, f)

    def _derive_key(self):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(self.password)

    def encrypt_data(self, data, student_name):
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        
        pad_len = 16 - (len(data) % 16)
        padded_data = data + bytes([pad_len] * pad_len)
        
        encrypted_data = iv + encryptor.update(padded_data) + encryptor.finalize()
        
        
        file_path = f"encodings/{student_name}.enc"
        with open(file_path, 'wb') as f:
            f.write(encrypted_data)
        
        
        file_hash = hashlib.sha256(encrypted_data).hexdigest()
        self._save_hash(student_name, file_hash)
        
        return file_path

    def decrypt_data(self, student_name):
        file_path = f"encodings/{student_name}.enc"
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No encoding found for {student_name}")
        
        with open(file_path, 'rb') as f:
            encrypted_data = f.read()
        
        
        current_hash = hashlib.sha256(encrypted_data).hexdigest()
        stored_hash = self._get_hash(student_name)
        
        if current_hash != stored_hash:
            raise PermissionError(f"Integrity check failed for {student_name}! The file may have been modified.")
        
       
        iv = encrypted_data[:16]
        cipher_data = encrypted_data[16:]
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        decrypted_padded_data = decryptor.update(cipher_data) + decryptor.finalize()
        
        
        pad_len = decrypted_padded_data[-1]
        decrypted_data = decrypted_padded_data[:-pad_len]
        
        return decrypted_data

    def _save_hash(self, student_name, file_hash):
        with open(self.hashes_file, 'r') as f:
            hashes_data = json.load(f)
        
        hashes_data[student_name] = file_hash
        
        with open(self.hashes_file, 'w') as f:
            json.dump(hashes_data, f)

    def _get_hash(self, student_name):
        with open(self.hashes_file, 'r') as f:
            hashes_data = json.load(f)
        return hashes_data.get(student_name)

    def list_encrypted_students(self):
        with open(self.hashes_file, 'r') as f:
            hashes_data = json.load(f)
        return list(hashes_data.keys())
