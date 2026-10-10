import { Outlet } from 'react-router-dom';

export default function AuthLayout() {
  return (
    <main className="login-page">
      <Outlet />
    </main>
  );
}
