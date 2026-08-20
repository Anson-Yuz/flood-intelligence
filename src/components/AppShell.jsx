import {
  BellRinging,
  Crosshair,
  Flask,
  HardDrives,
  LockKey,
  MapTrifold,
  SignOut,
  UserCircle,
  WaveSine,
  Wrench,
} from "@phosphor-icons/react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useAlertVisual } from "../context/AlertVisualContext";

const navigation = [
  { to: "/", end: true, label: "事件研判", shortLabel: "研判", icon: Crosshair },
  { to: "/overview", label: "全域态势", shortLabel: "态势", icon: MapTrifold },
  { to: "/events", label: "预警事件", shortLabel: "事件", icon: BellRinging },
  { to: "/simulator", label: "推演沙盘", shortLabel: "推演", icon: Flask },
  { to: "/maintenance", label: "路况养护", shortLabel: "养护", icon: Wrench },
  { to: "/devices", label: "设备运维", shortLabel: "设备", icon: HardDrives },
  { to: "/audit", label: "审计存证", shortLabel: "审计", icon: LockKey },
];

function getUserRole(user) {
  if (typeof user?.role === "string") return user.role;
  return user?.role?.name || user?.roleName || "平台用户";
}

export function AppShell() {
  const { user, logout, isLoggingOut, isStaticDemo } = useAuth();
  const { level } = useAlertVisual();
  const location = useLocation();
  const navigate = useNavigate();
  const displayName = user?.displayName || user?.name || user?.username || "当前用户";
  const role = getUserRole(user);
  const visualLevel = location.pathname === "/" ? "critical" : location.pathname === "/overview" ? level : "none";

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
    }
  };

  return (
    <div className={`app-shell alert-visual-frame alert-visual-frame--${visualLevel}`} data-alert-level={visualLevel}>
      <aside className="app-sidebar">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            <WaveSine size={24} weight="bold" />
          </div>
          <div className="brand-copy">
            <strong>预鉴</strong>
            <span>城市道路风险预判平台</span>
          </div>
        </div>

        <nav className="primary-navigation" aria-label="主导航">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => `navigation-link ${isActive ? "is-active" : ""}`}
              >
                <Icon size={20} weight="fill" />
                <span className="navigation-label">{item.label}</span>
                <span className="navigation-short-label">{item.shortLabel}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-system-state">
          <span className="system-online-dot" />
          <div>
            <strong>{isStaticDemo ? "公开演示运行中" : "平台运行正常"}</strong>
            <span>{isStaticDemo ? "不连接真实设备" : "41 / 42 台在线"}</span>
          </div>
        </div>

        <div className="sidebar-user">
          <UserCircle size={30} weight="fill" />
          <div><strong title={displayName}>{displayName}</strong><span title={role}>{role}</span></div>
          <button
            type="button"
            aria-label={isLoggingOut ? "正在退出登录" : "退出登录"}
            title={isLoggingOut ? "正在退出…" : "退出登录"}
            onClick={handleLogout}
            disabled={isLoggingOut}
            aria-busy={isLoggingOut}
          >
            <SignOut size={18} />
          </button>
        </div>
      </aside>

      <div className="app-content">
        <Outlet />
      </div>
    </div>
  );
}

export default AppShell;
