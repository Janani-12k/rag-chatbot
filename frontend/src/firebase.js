// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
import { getFirestore } from "firebase/firestore";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyC9KoQqSqWLgIhvmqrqOXq0R7f8ITwglbo",
  authDomain: "ragbot-879ca.firebaseapp.com",
  projectId: "ragbot-879ca",
  storageBucket: "ragbot-879ca.firebasestorage.app",
  messagingSenderId: "396651189334",
  appId: "1:396651189334:web:26c83ff30ca635a7e5d7f7",
  measurementId: "G-GJ61CPTYCQ"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);
export const db = getFirestore(app);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();