import os
import json
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

class SecurityManager:
    def __init__(self, password, salt=None):
        self.password = password.encode()
        
        self.salt = salt if salt is not None else os.urandom(16)
        self.key = self._derive_key()
        

    def _derive_key(self):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,               
            salt=self.salt,
            iterations=600000,       
            backend=default_backend()
        )
        return kdf.derive(self.password)

    def encrypt_data(self, data, student_name):
        
        nonce = os.urandom(12)
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(nonce), backend=default_backend())
        encryptor = cipher.encryptor()
        
        encrypted_data = encryptor.update(data) + encryptor.finalize()
        tag = encryptor.tag
        
        payload = self.salt + nonce + tag + encrypted_data
        
    
        file_path = f"encodings/{student_name}.enc"
        os.makedirs("encodings", exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(payload)
        
        return file_path

    def decrypt_data(self, student_name):
        file_path = f"encodings/{student_name}.enc"
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No encoding found for {student_name}")
        
        with open(file_path, 'rb') as f:
            payload = f.read()
        
        # Extract components from the payload
        salt = payload[:16]           
        nonce = payload[16:28]        
        tag = payload[28:44]         
        encrypted_data = payload[44:]
        
        temp_manager = SecurityManager(self.password.decode(), salt=salt)
        
        
        cipher = Cipher(algorithms.AES(temp_manager.key), modes.GCM(nonce, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
        
        return decrypted_data
        

    
