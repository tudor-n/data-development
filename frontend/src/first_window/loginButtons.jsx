import React from 'react';
import './loginButtons.css';

function LoginButtons({ onLogin, onSignup }) {
  return (
    <div className="lb-container">
      <button
        className="lb-btn lb-login"
        type="button"
        onClick={onLogin || (() => console.log('Login clicked'))}
      >
        Login
      </button>

      <button
        className="lb-btn lb-signup"
        type="button"
        onClick={onSignup || (() => console.log('Sign up clicked'))}
      >
        Sign up
      </button>
    </div>
  );
}

export default LoginButtons;