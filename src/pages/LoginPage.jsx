import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle,
  CloudRain,
  Database,
  Eye,
  EyeSlash,
  LockKey,
  ShieldCheck,
  User,
  Warning,
  WaveSine,
} from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import { assetPath } from "../config/runtime";

function safeReturnPath(value) {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//") && value !== "/login"
    ? value
    : "/";
}

export function LoginPage() {
  const {
    login,
    error: authError,
    clearError,
    isSubmitting,
    isAuthenticated,
    rememberedUsername,
    isStaticDemo,
    enterStaticDemo,
  } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState(rememberedUsername);
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(Boolean(rememberedUsername));
  const [showPassword, setShowPassword] = useState(false);
  const [validationError, setValidationError] = useState("");

  useEffect(() => () => clearError(), [clearError]);

  if (isAuthenticated) return <Navigate to="/" replace />;

  const handleDemoEnter = () => {
    enterStaticDemo();
    navigate(safeReturnPath(location.state?.from), { replace: true });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const cleanUsername = username.trim();
    if (!cleanUsername || !password) {
      setValidationError("请输入用户名和密码");
      return;
    }
    setValidationError("");
    clearError();
    try {
      await login({ username: cleanUsername, password, remember });
      navigate(safeReturnPath(location.state?.from), { replace: true });
    } catch {
      // AuthContext exposes the server message in authError.
    }
  };

  const activeError = validationError || authError;

  return (
    <main className="login-page">
      <section
        className="login-visual"
        aria-label="预鉴平台能力概览"
        style={{ "--login-background-image": "url(" + assetPath("assets/tunnel-water-overlay.png") + ")" }}
      >
        <div className="login-visual-backdrop" aria-hidden="true" />
        <header className="login-brand">
          <div className="login-brand-icon"><WaveSine size={28} weight="bold" /></div>
          <div><strong>预鉴</strong><span>城市道路风险预判平台</span></div>
        </header>

        <div className="login-visual-copy">
          <span className="login-kicker"><ShieldCheck size={17} weight="fill" />城市道路安全运行工作台</span>
          <h1>预见道路风险，<br />留出处置时间</h1>
          <p>融合道路积水短临预报、路面状态监测与可审计处置链，为值班人员提供可信的前置决策依据。</p>
          <ul className="login-capabilities">
            <li><CloudRain size={19} weight="fill" /><div><strong>15–60分钟短临预报</strong><span>实时研判积水深度、达险时间与置信度</span></div></li>
            <li><Database size={19} weight="fill" /><div><strong>云边协同多模态感知</strong><span>摄像头、DEM与气象数据持续交叉校验</span></div></li>
            <li><CheckCircle size={19} weight="fill" /><div><strong>确定性决策全程可审计</strong><span>推理依据、人工操作和终端回执完整留痕</span></div></li>
          </ul>
        </div>

        <footer className="login-visual-footer">
          <span><i />{isStaticDemo ? "静态演示已就绪" : "平台服务运行中"}</span>
          <span>{isStaticDemo ? "不连接真实系统" : "会话受保护"}</span>
        </footer>
      </section>

      <section className="login-panel">
        <div className="login-form-shell">
          <div className="login-form-heading">
            <span className="login-panel-mark"><LockKey size={20} weight="fill" /></span>
            <div>
              <h2>{isStaticDemo ? "进入公开演示" : "登录指挥工作台"}</h2>
              <p>{isStaticDemo ? "无需账号，数据与操作均为只读模拟" : "请使用已授权的政务账号继续"}</p>
            </div>
          </div>

          {isStaticDemo ? (
            <div className="static-demo-card">
              <div className="static-demo-badge"><ShieldCheck size={17} weight="fill" />GitHub Pages 公开演示</div>
              <h3>浏览完整平台，不连接真实系统</h3>
              <p>可体验深圳十区地图、真实场景照片、预警光晕、事件研判、推演和养护页面。所有处置操作仅在当前浏览器中模拟。</p>
              <ul>
                <li><CheckCircle size={16} weight="fill" />不访问后端与数据库</li>
                <li><CheckCircle size={16} weight="fill" />不发送硬件指令或上报</li>
                <li><CheckCircle size={16} weight="fill" />关闭页面后会话自动失效</li>
              </ul>
              <button className="login-submit" type="button" onClick={handleDemoEnter}>
                进入访客演示<ArrowRight size={19} weight="bold" />
              </button>
            </div>
          ) : (
          <form className="login-form" onSubmit={handleSubmit} noValidate>
            {activeError && (
              <div className="login-error" role="alert">
                <Warning size={18} weight="fill" />
                <span>{activeError}</span>
              </div>
            )}

            <label className="login-field">
              <span>用户名</span>
              <div className="login-input-wrap">
                <User size={19} />
                <input
                  type="text"
                  value={username}
                  onChange={(event) => {
                    setUsername(event.target.value);
                    setValidationError("");
                    clearError();
                  }}
                  autoComplete="username"
                  placeholder="请输入用户名"
                  disabled={isSubmitting}
                  autoFocus
                />
              </div>
            </label>

            <label className="login-field">
              <span>密码</span>
              <div className="login-input-wrap">
                <LockKey size={19} />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    setValidationError("");
                    clearError();
                  }}
                  autoComplete="current-password"
                  placeholder="请输入密码"
                  disabled={isSubmitting}
                />
                <button
                  className="password-toggle"
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "隐藏密码" : "显示密码"}
                  aria-pressed={showPassword}
                  disabled={isSubmitting}
                >
                  {showPassword ? <EyeSlash size={19} /> : <Eye size={19} />}
                </button>
              </div>
            </label>

            <label className="remember-control">
              <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} disabled={isSubmitting} />
              <span><i><CheckCircle size={15} weight="fill" /></i>记住登录</span>
              <small>延长会话并记住用户名</small>
            </label>

            <button className="login-submit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? <><i className="login-spinner" />正在验证身份…</> : <>进入平台<ArrowRight size={19} weight="bold" /></>}
            </button>
          </form>
          )}

          <div className="login-security-note">
            <ShieldCheck size={17} weight="fill" />
            <span>{isStaticDemo ? "公开版本为只读前端演示，不连接真实设备、数据库或处置系统。" : "系统仅供授权人员使用，登录与操作行为将写入安全审计日志。"}</span>
          </div>
        </div>
        <footer className="login-panel-footer">预鉴平台 · {isStaticDemo ? "公开只读演示" : "统一身份认证"}</footer>
      </section>
    </main>
  );
}

export default LoginPage;
