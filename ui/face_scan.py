import cv2
import numpy as np
import os
import logging
import time

logger = logging.getLogger(__name__)

# Paths to models
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
YUNET_PATH = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
SFACE_PATH = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")
PROFILE_PATH = os.path.join(MODELS_DIR, "creator_profile.npy")

class FaceScanner:
    def __init__(self):
        self.detector = None
        self.recognizer = None
        self.input_size = (320, 320)
        
    def _init_models(self):
        if self.detector is None:
            if not os.path.exists(YUNET_PATH) or not os.path.exists(SFACE_PATH):
                raise FileNotFoundError("ONNX models not found in models directory.")
                
            self.detector = cv2.FaceDetectorYN.create(
                model=YUNET_PATH,
                config="",
                input_size=self.input_size,
                score_threshold=0.6,
                nms_threshold=0.3,
                top_k=5000
            )
            self.recognizer = cv2.FaceRecognizerSF.create(
                model=SFACE_PATH,
                config=""
            )

    def _capture_and_detect(self):
        self._init_models()
        
        best_overall_face = None
        best_overall_frame = None
        max_area_overall = 0
        last_frame = None
        
        # Try multiple camera indices (0 to 2) in case index 0 is a virtual camera (like OBS)
        for cam_idx in [0, 1, 2]:
            # Use CAP_DSHOW as it is required to turn on the LED and capture light on some hardware
            cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                # Fallback without CAP_DSHOW if it fails to open
                cap = cv2.VideoCapture(cam_idx)
                if not cap.isOpened():
                    continue
                
            logger.info(f"Testing webcam index {cam_idx}...")
            
            # Read a few frames to let the camera adjust lighting/focus
            for _ in range(15):
                cap.read()
                time.sleep(0.05)
                
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                continue
                
            last_frame = frame
            # Save debug frame for each camera index
            cv2.imwrite(f"debug_webcam_frame_{cam_idx}.jpg", frame)
            
            h, w, _ = frame.shape
            self.detector.setInputSize((w, h))
            
            _, faces = self.detector.detect(frame)
            if faces is not None and len(faces) > 0:
                # We found a face! Check if it's the largest one we've seen
                for face in faces:
                    area = face[2] * face[3]
                    if area > max_area_overall:
                        max_area_overall = area
                        best_overall_face = face
                        best_overall_frame = frame
                        
                # If we found a good face, stop checking other cameras
                if best_overall_face is not None:
                    logger.info(f"Face detected on camera index {cam_idx}")
                    break
                    
        if best_overall_face is None:
            logger.info("No face detected on any camera.")
            if last_frame is None:
                logger.error("Could not read from any webcam.")
            return last_frame, None
            
        return best_overall_frame, best_overall_face

    def register_creator(self) -> str:
        """Takes a picture and saves the face embedding."""
        try:
            frame, face = self._capture_and_detect()
            if face is None:
                return "I couldn't detect a face. Please make sure you are looking at the camera in a well-lit room."
                
            # Extract features
            aligned_face = self.recognizer.alignCrop(frame, face)
            feature = self.recognizer.feature(aligned_face)
            
            # Save feature profile
            np.save(PROFILE_PATH, feature)
            logger.info("Creator profile saved successfully.")
            return "Facial scan complete. You are now registered as the creator, Shawn Kieffer Goyena."
            
        except Exception as e:
            logger.error(f"Error registering face: {e}")
            return "There was an error accessing the biometric scanner."

    def verify_creator(self) -> str:
        """Compares current face to saved creator profile."""
        try:
            if not os.path.exists(PROFILE_PATH):
                return "Creator profile not found. Please register your face first."
                
            frame, face = self._capture_and_detect()
            if face is None:
                return "I couldn't detect a face in the camera frame."
                
            creator_feature = np.load(PROFILE_PATH)
            
            aligned_face = self.recognizer.alignCrop(frame, face)
            current_feature = self.recognizer.feature(aligned_face)
            
            # Compare features (Cosine similarity: threshold is 0.363 for SFace)
            score = self.recognizer.match(creator_feature, current_feature, cv2.FaceRecognizerSF_FR_COSINE)
            
            logger.info(f"Face match score: {score}")
            if score >= 0.363:
                return "Identity verified. Welcome back, creator Shawn Kieffer Goyena."
            else:
                return "Access Denied. You do not match the creator's biometric profile."
                
        except Exception as e:
            logger.error(f"Error verifying face: {e}")
            return "There was an error accessing the biometric scanner."
