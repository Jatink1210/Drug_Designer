// Cypress E2E support file

import './commands';
import 'cypress-file-upload';

// Hide fetch/XHR requests from command log
const app = window.top;
if (app && !app.document.head.querySelector('[data-hide-command-log-request]')) {
  const style = app.document.createElement('style');
  style.innerHTML = '.command-name-request, .command-name-xhr { display: none }';
  style.setAttribute('data-hide-command-log-request', '');
  app.document.head.appendChild(style);
}

// Preserve cookies between tests
Cypress.Cookies.defaults({
  preserve: ['session', 'auth_token'],
});

// Global error handling
Cypress.on('uncaught:exception', (err, runnable) => {
  // Returning false prevents Cypress from failing the test
  // Only for specific errors we want to ignore
  if (err.message.includes('ResizeObserver loop')) {
    return false;
  }
  return true;
});

// Custom assertions
chai.use((chai, utils) => {
  chai.Assertion.addMethod('oneOf', function (list) {
    const obj = utils.flag(this, 'object');
    new chai.Assertion(list).to.include(obj);
  });
});
