import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';

import Login from './pages/Login';

import StudentDashboard from './pages/student/Dashboard';
import Chat from './pages/student/Chat';
import Chapter from './pages/student/Chapter';
import Story from './pages/student/Story';
import Memories from './pages/student/Memories';
import Goals from './pages/student/Goals';
import Progress from './pages/student/Progress';
import Profile from './pages/student/Profile';

import TeacherDashboard from './pages/teacher/Dashboard';
import Students from './pages/teacher/Students';
import StudentCreate from './pages/teacher/StudentCreate';
import StudentDetail from './pages/teacher/StudentDetail';
import TeacherGoals from './pages/teacher/Goals';
import TeacherAnalytics from './pages/teacher/Analytics';

import AdminDashboard from './pages/admin/Dashboard';
import Teachers from './pages/admin/Teachers';
import TeacherCreate from './pages/admin/TeacherCreate';
import AdminAnalytics from './pages/admin/Analytics';
import Settings from './pages/admin/Settings';

const S = ({ children }) => <ProtectedRoute role="student">{children}</ProtectedRoute>;
const T = ({ children }) => <ProtectedRoute role="teacher">{children}</ProtectedRoute>;
const A = ({ children }) => <ProtectedRoute role="admin">{children}</ProtectedRoute>;

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route path="/student/dashboard" element={<S><StudentDashboard /></S>} />
          <Route path="/student/chat" element={<S><Chat /></S>} />
          <Route path="/student/chapter" element={<S><Chapter /></S>} />
          <Route path="/student/story" element={<S><Story /></S>} />
          <Route path="/student/memories" element={<S><Memories /></S>} />
          <Route path="/student/goals" element={<S><Goals /></S>} />
          <Route path="/student/progress" element={<S><Progress /></S>} />
          <Route path="/student/profile" element={<S><Profile /></S>} />

          <Route path="/teacher/dashboard" element={<T><TeacherDashboard /></T>} />
          <Route path="/teacher/students" element={<T><Students /></T>} />
          <Route path="/teacher/students/new" element={<T><StudentCreate /></T>} />
          <Route path="/teacher/students/:id" element={<T><StudentDetail /></T>} />
          <Route path="/teacher/goals" element={<T><TeacherGoals /></T>} />
          <Route path="/teacher/analytics" element={<T><TeacherAnalytics /></T>} />

          <Route path="/admin/dashboard" element={<A><AdminDashboard /></A>} />
          <Route path="/admin/teachers" element={<A><Teachers /></A>} />
          <Route path="/admin/teachers/new" element={<A><TeacherCreate /></A>} />
          <Route path="/admin/analytics" element={<A><AdminAnalytics /></A>} />
          <Route path="/admin/settings" element={<A><Settings /></A>} />

          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
