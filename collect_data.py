import cv2
import os
import face_recognition

def collect_data(student_name):
    
    dataset_path = f"dataset/{student_name}"
    if not os.path.exists(dataset_path):
        os.makedirs(dataset_path)
        print(f"Created directory: {dataset_path}")
    else:
        print(f"Directory already exists: {dataset_path}")

    
    video_capture = cv2.VideoCapture(0)
    
    count = 0
    print(f"Starting data collection for {student_name}. Press 'c' to capture, 'q' to quit.")
    print("Capture at least 5 images with different angles and expressions.")

    while True:
       
        ret, frame = video_capture.read()
        if not ret:
            print("Failed to capture image")
            break

        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        
        face_locations = face_recognition.face_locations(rgb_frame)

        
        for (top, right, bottom, left) in face_locations:
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)

       
        cv2.imshow('Capture Faces - Press C to Capture, Q to Quit', frame)

        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            if len(face_locations) == 1:
                
                top, right, bottom, left = face_locations[0]
                
                face_image = frame[top:bottom, left:right]
                
                count += 1
                img_name = f"{dataset_path}/{count}.jpg"
                cv2.imwrite(img_name, face_image)
                print(f"Captured {img_name}")
            elif len(face_locations) == 0:
                print("No face detected! Try again.")
            else:
                print("Multiple faces detected! Please ensure only one student is in frame.")

        
        elif key == ord('q'):
            break

    
    video_capture.release()
    cv2.destroyAllWindows()
    print(f"Data collection for {student_name} finished. {count} images captured.")

if __name__ == "__main__":
    name = input("Enter student name: ")
    collect_data(name)
