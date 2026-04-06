import sys
import os
import cv2
import pickle
import numpy as np
import pandas as pd
from datetime import datetime
import face_recognition
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QMessageBox, QGroupBox, QGridLayout
)
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, Qt
from PyQt5.QtGui import QImage, QPixmap, QFont

from security import SecurityManager

# --- Thread Workers ---

class CameraCollectionWorker(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    status_signal = pyqtSignal(str)

    def __init__(self, student_name):
        super().__init__()
        self.running = True
        self.student_name = student_name
        self.dataset_path = f"dataset/{self.student_name}"
        self.capture_flag = False
        self.image_count = 0

        if not os.path.exists(self.dataset_path):
            os.makedirs(self.dataset_path)

    def run(self):
        cap = cv2.VideoCapture(0)
        while self.running:
            ret, frame = cap.read()
            if ret:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_frame)

                # Draw boxes for visual feedback
                for (top, right, bottom, left) in face_locations:
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)

                if self.capture_flag:
                    if len(face_locations) == 1:
                        top, right, bottom, left = face_locations[0]
                        face_image = frame[top:bottom, left:right]
                        self.image_count += 1
                        img_path = f"{self.dataset_path}/{self.image_count}.jpg"
                        cv2.imwrite(img_path, face_image)
                        self.status_signal.emit(f"Captured Image {self.image_count}")
                    elif len(face_locations) == 0:
                        self.status_signal.emit("No face detected! Try again.")
                    else:
                        self.status_signal.emit("Multiple faces detected! Please ensure only one student is in frame.")
                    self.capture_flag = False

                self.change_pixmap_signal.emit(frame)
        cap.release()

    def capture_frame(self):
        self.capture_flag = True

    def stop(self):
        self.running = False
        self.wait()


class EncodingWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, password):
        super().__init__()
        self.password = password

    def run(self):
        try:
            security = SecurityManager(self.password)
            dataset_dir = "dataset"
            
            if not os.path.exists(dataset_dir):
                self.log_signal.emit("Error: Dataset directory not found!")
                self.finished_signal.emit()
                return

            students = os.listdir(dataset_dir)
            if not students:
                self.log_signal.emit("Error: Dataset is empty!")
                self.finished_signal.emit()
                return

            for student_name in students:
                student_path = os.path.join(dataset_dir, student_name)
                if not os.path.isdir(student_path): continue
                
                self.log_signal.emit(f"Processing student: {student_name}")
                all_encodings = []
                
                for img_name in os.listdir(student_path):
                    img_path = os.path.join(student_path, img_name)
                    try:
                        image = face_recognition.load_image_file(img_path)
                        encodings = face_recognition.face_encodings(image)
                        if len(encodings) > 0:
                            all_encodings.append(encodings[0])
                        else:
                            self.log_signal.emit(f"No face found in {img_name}")
                    except Exception as e:
                        self.log_signal.emit(f"Error processing {img_name}: {e}")
                
                if all_encodings:
                    encoded_data = pickle.dumps(all_encodings)
                    security.encrypt_data(encoded_data, student_name)
                    self.log_signal.emit(f"Successfully secured encodings for {student_name}")
                else:
                    self.log_signal.emit(f"No valid encodings for {student_name}")

            self.log_signal.emit("Extraction Process Complete.")
        except Exception as e:
            self.log_signal.emit(f"Critical Error: {e}")
        self.finished_signal.emit()


class RecognitionWorker(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, password):
        super().__init__()
        self.running = True
        self.password = password
        self.known_face_encodings = []
        self.known_face_names = []
        self.logged_today = set()
        self.log_file = "logs/attendance.csv"
        self.setup_logs()

    def setup_logs(self):
        if not os.path.exists("logs"): os.makedirs("logs")
        if not os.path.exists(self.log_file):
            pd.DataFrame(columns=["Name", "Timestamp", "Confidence"]).to_csv(self.log_file, index=False)

    def load_encodings(self):
        try:
            security = SecurityManager(self.password)
            students = security.list_encrypted_students()
            if not students:
                self.error_signal.emit("No secured encodings found. Please run extraction first.")
                return False

            self.log_signal.emit("Loading and decrypting signatures...")
            for student_name in students:
                decrypted_data = security.decrypt_data(student_name)
                encodings = pickle.loads(decrypted_data)
                for encoding in encodings:
                    self.known_face_encodings.append(encoding)
                    self.known_face_names.append(student_name)
            return True
        except Exception as e:
            self.error_signal.emit(f"Decryption failed. Invalid password or tampered data.\nDetails: {e}")
            return False

    def run(self):
        if not self.load_encodings():
            return

        cap = cv2.VideoCapture(0)
        self.log_signal.emit("Camera initialized. Tracking started.")
        while self.running:
            ret, frame = cap.read()
            if ret:
                # Resize frame for performance
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

                face_locations = face_recognition.face_locations(rgb_small_frame)
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

                for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                    top *= 4; right *= 4; bottom *= 4; left *= 4

                    matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding)
                    name = "Unknown"
                    confidence = 0

                    face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                    if len(face_distances) > 0:
                        best_match_index = np.argmin(face_distances)
                        if matches[best_match_index]:
                            name = self.known_face_names[best_match_index]
                            confidence = max(0, 1 - face_distances[best_match_index]) * 100

                    color = (0, 0, 255) if name == "Unknown" else (0, 255, 0)
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
                    label = f"{name} ({confidence:.1f}%)" if name != "Unknown" else name
                    cv2.putText(frame, label, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)

                    if name != "Unknown" and name not in self.logged_today:
                        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        new_log = pd.DataFrame([[name, time_str, f"{confidence:.1f}%"]], columns=["Name", "Timestamp", "Confidence"])
                        new_log.to_csv(self.log_file, mode='a', header=False, index=False)
                        self.logged_today.add(name)
                        self.log_signal.emit(f"> Attendance recognized: {name}")

                self.change_pixmap_signal.emit(frame)
        cap.release()

    def stop(self):
        self.running = False
        self.wait()


# --- Main GUI Application ---

class BiometricsGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Biometric Face Recognition System")
        self.resize(900, 700)

        # Worker placeholders to prevent accidental multiple cameras opening
        self.collection_worker = None
        self.recognition_worker = None

        self.setup_ui()
        self.apply_dark_theme()

    def apply_dark_theme(self):
        dark_stylesheet = """
        QMainWindow { background-color: #1e1e2e; }
        QLabel { color: #cdd6f4; font-size: 14px; }
        QPushButton {
            background-color: #89b4fa;
            color: #11111b;
            border-radius: 6px;
            padding: 8px;
            font-weight: bold;
            font-size: 14px;
        }
        QPushButton:hover { background-color: #b4befe; }
        QPushButton:disabled { background-color: #45475a; color: #a6adc8; }
        QLineEdit, QTextEdit {
            background-color: #313244;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 4px;
            padding: 4px;
        }
        QTabWidget::pane { border: 1px solid #45475a; border-radius: 6px; background-color: #181825;}
        QTabBar::tab {
            background: #313244;
            color: #cdd6f4;
            padding: 10px 20px;
            margin: 2px;
            border-radius: 4px;
        }
        QTabBar::tab:selected { background: #89b4fa; color: #11111b; font-weight: bold;}
        QGroupBox { color: #89b4fa; border: 1px solid #45475a; border-radius: 6px; margin-top: 10px; padding-top: 10px;}
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """
        self.setStyleSheet(dark_stylesheet)

    def setup_ui(self):
        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        tabs.addTab(self.create_collection_tab(), "1. Data Collection")
        tabs.addTab(self.create_extraction_tab(), "2. Feature Extraction")
        tabs.addTab(self.create_recognition_tab(), "3. Live Identification")

        tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        # Cleanly stop any running cameras when switching tabs
        if self.collection_worker and self.collection_worker.isRunning():
            self.collection_worker.stop()
        if self.recognition_worker and self.recognition_worker.isRunning():
            self.recognition_worker.stop()

        self.coll_video_label.setText("Camera Feed Offline")
        self.rec_video_label.setText("Camera Feed Offline")
        self.coll_start_btn.setEnabled(True)
        self.rec_start_btn.setEnabled(True)

    def closeEvent(self, event):
        self.on_tab_changed(-1) # Stop threads
        event.accept()

    def update_image(self, cv_img, target_label):
        """Convert cv ndarray from BGR to QPixmap for displaying in QLabel"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(target_label.width(), target_label.height(), Qt.KeepAspectRatio)
        target_label.setPixmap(QPixmap.fromImage(p))

    # --- Tab 1: Collection ---
    def create_collection_tab(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Left Panel (Controls)
        control_group = QGroupBox("Student Registration")
        control_layout = QVBoxLayout(control_group)
        
        control_layout.addWidget(QLabel("Student Name:"))
        self.coll_name_input = QLineEdit()
        control_layout.addWidget(self.coll_name_input)
        
        self.coll_start_btn = QPushButton("Start Camera")
        self.coll_capture_btn = QPushButton("Capture Face")
        self.coll_capture_btn.setEnabled(False)
        self.coll_stop_btn = QPushButton("Stop Camera")
        self.coll_stop_btn.setEnabled(False)

        self.coll_status_label = QLabel("Status: Ready")
        
        control_layout.addWidget(self.coll_start_btn)
        control_layout.addWidget(self.coll_capture_btn)
        control_layout.addWidget(self.coll_stop_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.coll_status_label)

        # Right Panel (Video)
        self.coll_video_label = QLabel("Camera Feed Offline")
        self.coll_video_label.setAlignment(Qt.AlignCenter)
        self.coll_video_label.setStyleSheet("border: 2px dashed #45475a; border-radius: 8px; font-size: 18pt;")
        self.coll_video_label.setMinimumSize(640, 480)

        layout.addWidget(control_group, 1)
        layout.addWidget(self.coll_video_label, 3)

        # Connections
        self.coll_start_btn.clicked.connect(self.start_collection)
        self.coll_capture_btn.clicked.connect(self.capture_collection)
        self.coll_stop_btn.clicked.connect(self.stop_collection)

        return widget

    def start_collection(self):
        name = self.coll_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Please enter a student name.")
            return

        self.coll_start_btn.setEnabled(False)
        self.coll_name_input.setEnabled(False)
        self.coll_capture_btn.setEnabled(True)
        self.coll_stop_btn.setEnabled(True)

        self.collection_worker = CameraCollectionWorker(name)
        self.collection_worker.change_pixmap_signal.connect(lambda img: self.update_image(img, self.coll_video_label))
        self.collection_worker.status_signal.connect(self.coll_status_label.setText)
        self.collection_worker.start()

    def capture_collection(self):
        if self.collection_worker:
            self.collection_worker.capture_frame()

    def stop_collection(self):
        if self.collection_worker:
            self.collection_worker.stop()
            self.collection_worker = None
        self.coll_video_label.setText("Camera Feed Offline")
        self.coll_start_btn.setEnabled(True)
        self.coll_name_input.setEnabled(True)
        self.coll_capture_btn.setEnabled(False)
        self.coll_stop_btn.setEnabled(False)
        self.coll_status_label.setText("Status: Ready")

    # --- Tab 2: Extraction ---
    def create_extraction_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        control_group = QGroupBox("Security & Feature Encoding")
        control_layout = QGridLayout(control_group)

        control_layout.addWidget(QLabel("Master Password (AES-256):"), 0, 0)
        self.ext_pwd_input = QLineEdit()
        self.ext_pwd_input.setEchoMode(QLineEdit.Password)
        control_layout.addWidget(self.ext_pwd_input, 0, 1)

        self.ext_start_btn = QPushButton("Extract & Secure Features")
        control_layout.addWidget(self.ext_start_btn, 1, 0, 1, 2)

        self.ext_logs = QTextEdit()
        self.ext_logs.setReadOnly(True)

        layout.addWidget(control_group)
        layout.addWidget(QLabel("Extraction Logs:"))
        layout.addWidget(self.ext_logs)

        self.ext_start_btn.clicked.connect(self.start_extraction)
        return widget

    def start_extraction(self):
        pwd = self.ext_pwd_input.text()
        if not pwd:
            QMessageBox.warning(self, "Security Error", "Master password is required for encryption.")
            return

        self.ext_start_btn.setEnabled(False)
        self.ext_logs.clear()
        
        self.encoding_worker = EncodingWorker(pwd)
        self.encoding_worker.log_signal.connect(self.ext_logs.append)
        self.encoding_worker.finished_signal.connect(lambda: self.ext_start_btn.setEnabled(True))
        self.encoding_worker.start()

    # --- Tab 3: Recognition ---
    def create_recognition_tab(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Left Panel (Video & Controls)
        video_group = QVBoxLayout()
        self.rec_pwd_input = QLineEdit()
        self.rec_pwd_input.setEchoMode(QLineEdit.Password)
        self.rec_pwd_input.setPlaceholderText("Enter Master Password to Decrypt...")
        
        btn_layout = QHBoxLayout()
        self.rec_start_btn = QPushButton("Start Live Monitoring")
        self.rec_stop_btn = QPushButton("Stop Monitoring")
        self.rec_stop_btn.setEnabled(False)
        btn_layout.addWidget(self.rec_start_btn)
        btn_layout.addWidget(self.rec_stop_btn)

        self.rec_video_label = QLabel("Camera Feed Offline")
        self.rec_video_label.setAlignment(Qt.AlignCenter)
        self.rec_video_label.setStyleSheet("border: 2px dashed #45475a; border-radius: 8px; font-size: 18pt;")
        self.rec_video_label.setMinimumSize(640, 480)

        video_group.addWidget(self.rec_pwd_input)
        video_group.addLayout(btn_layout)
        video_group.addWidget(self.rec_video_label)

        # Right Panel (Logs)
        log_group = QGroupBox("Live Attendance Logs")
        log_layout = QVBoxLayout(log_group)
        self.rec_logs = QTextEdit()
        self.rec_logs.setReadOnly(True)
        log_layout.addWidget(self.rec_logs)

        layout.addLayout(video_group, 3)
        layout.addWidget(log_group, 1)

        self.rec_start_btn.clicked.connect(self.start_recognition)
        self.rec_stop_btn.clicked.connect(self.stop_recognition)

        return widget

    def start_recognition(self):
        pwd = self.rec_pwd_input.text()
        if not pwd:
            QMessageBox.warning(self, "Security Error", "Master password is required for decryption.")
            return

        self.rec_start_btn.setEnabled(False)
        self.rec_pwd_input.setEnabled(False)
        self.rec_stop_btn.setEnabled(True)
        self.rec_logs.clear()

        self.recognition_worker = RecognitionWorker(pwd)
        self.recognition_worker.change_pixmap_signal.connect(lambda img: self.update_image(img, self.rec_video_label))
        self.recognition_worker.log_signal.connect(self.rec_logs.append)
        
        # Define error slot
        def on_recognition_error(msg):
            QMessageBox.critical(self, "Decryption Error", msg)
            self.stop_recognition()
            
        self.recognition_worker.error_signal.connect(on_recognition_error)
        self.recognition_worker.start()

    def stop_recognition(self):
        if self.recognition_worker:
            self.recognition_worker.stop()
            self.recognition_worker = None
        self.rec_video_label.setText("Camera Feed Offline")
        self.rec_start_btn.setEnabled(True)
        self.rec_pwd_input.setEnabled(True)
        self.rec_stop_btn.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Modern font
    app.setFont(QFont("Inter", 10))
    
    window = BiometricsGUI()
    window.show()
    sys.exit(app.exec_())
