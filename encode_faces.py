import os
import face_recognition
import pickle
from security import SecurityManager
import getpass

def encode_and_secure(password):
    security = SecurityManager(password)
    dataset_dir = "dataset"
    
    if not os.path.exists(dataset_dir):
        print("Dataset directory not found!")
        return

    for student_name in os.listdir(dataset_dir):
        student_path = os.path.join(dataset_dir, student_name)
        if not os.path.isdir(student_path):
            continue
        
        print(f"Processing student: {student_name}")
        all_encodings = []
        
        for img_name in os.listdir(student_path):
            img_path = os.path.join(student_path, img_name)
            try:
                image = face_recognition.load_image_file(img_path)
                encodings = face_recognition.face_encodings(image)
                
                if len(encodings) > 0:
                    all_encodings.append(encodings[0])
                else:
                    print(f"No face found in {img_path}")
            except Exception as e:
                print(f"Error processing {img_path}: {e}")
        
        if all_encodings:
            # We take the average encoding if multiple images were captured
            # but for simplicity we can just store the list of encodings
            # The requirement is "Store feature vectors"
            encoded_data = pickle.dumps(all_encodings)
            
            # Encrypt and save
            security.encrypt_data(encoded_data, student_name)
            print(f"Successfully secured encodings for {student_name}")
        else:
            print(f"No encodings generated for {student_name}")

if __name__ == "__main__":
    pwd = getpass.getpass("Enter master password for encryption: ")
    encode_and_secure(pwd)
