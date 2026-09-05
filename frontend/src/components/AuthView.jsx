import { useState } from 'react';
import { Sparkles, ArrowLeft, AlertCircle, Shield, KeyRound, Mail, User } from 'lucide-react';
import { loginUser, registerUser } from '../api';

export default function AuthView({ onLoginSuccess, onBackToLanding, initialMode = 'login' }) {
  const [mode, setMode] = useState(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      let data;
      if (mode === 'login') {
        data = await loginUser(email, password);
      } else {
        data = await registerUser(email, password, name);
      }
      onLoginSuccess(data.user);
    } catch (err) {
      setError(err.message || 'Authentication failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      const data = await loginUser('dev@example.com', 'password123');
      onLoginSuccess(data.user);
    } catch (err) {
      setError(err.message || 'Demo login failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="beacon-auth-shell">
      <div className="beacon-auth-card">
        {onBackToLanding && (
          <button
            type="button"
            className="auth-back-btn"
            onClick={onBackToLanding}
            aria-label="Back to overview"
          >
            <ArrowLeft size={14} />
            <span>Back to overview</span>
          </button>
        )}

        <div className="auth-card__header">
          <div className="beacon-brand-mark" aria-hidden="true">
            <span className="beacon-brand-dot" />
          </div>
          <h1 className="auth-card__title">BEACON</h1>
          <p className="auth-card__tagline">Know what deserves your attention.</p>
          <p className="auth-card__subtitle">
            Attention-filtering intelligence for market changes that actually matter.
          </p>
        </div>

        <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'login'}
            className={`auth-tab ${mode === 'login' ? 'auth-tab--active' : ''}`}
            onClick={() => { setMode('login'); setError(null); }}
          >
            Log In
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'register'}
            className={`auth-tab ${mode === 'register' ? 'auth-tab--active' : ''}`}
            onClick={() => { setMode('register'); setError(null); }}
          >
            Create Account
          </button>
        </div>

        {error && (
          <div className="beacon-alert beacon-alert--error" role="alert">
            <AlertCircle size={16} className="alert-icon" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          {mode === 'register' && (
            <div className="form-field">
              <label htmlFor="auth-name" className="field-label">
                <User size={13} style={{ marginRight: '6px' }} />
                Full Name
              </label>
              <input
                id="auth-name"
                type="text"
                className="beacon-input"
                placeholder="e.g. Rahul Sharma"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={100}
                autoComplete="name"
              />
            </div>
          )}

          <div className="form-field">
            <label htmlFor="auth-email" className="field-label">
              <Mail size={13} style={{ marginRight: '6px' }} />
              Email Address
            </label>
            <input
              id="auth-email"
              type="email"
              className="beacon-input"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>

          <div className="form-field">
            <label htmlFor="auth-password" className="field-label">
              <KeyRound size={13} style={{ marginRight: '6px' }} />
              Password
            </label>
            <input
              id="auth-password"
              type="password"
              className="beacon-input"
              placeholder={mode === 'register' ? 'At least 8 characters' : 'Enter your password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={mode === 'register' ? 8 : 1}
              required
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            />
          </div>

          <button
            type="submit"
            className="beacon-btn beacon-btn--primary auth-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <span className="btn-loading-state">
                <span className="beacon-spinner-sm" />
                <span>Authenticating...</span>
              </span>
            ) : mode === 'login' ? (
              'Log In to Beacon'
            ) : (
              'Create Account & Enter'
            )}
          </button>
        </form>

        <div className="auth-divider">
          <span>or evaluation reviewer demo</span>
        </div>

        <button
          type="button"
          className="beacon-btn beacon-btn--demo"
          onClick={handleDemoLogin}
          disabled={loading}
          title="Log in with pre-seeded demo credentials"
        >
          <Sparkles size={15} style={{ marginRight: '6px', color: 'var(--beacon-gold)' }} />
          <span>Quick Demo Login (dev@example.com)</span>
        </button>

        <div className="auth-footer-note">
          <Shield size={12} style={{ marginRight: '4px', verticalAlign: '-1px' }} />
          <span>Stateless HS256 tokens · Scrypt password derivation · Zero tracking cookies</span>
        </div>
      </div>
    </div>
  );
}
