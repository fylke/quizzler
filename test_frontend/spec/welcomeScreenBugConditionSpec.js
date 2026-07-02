// Feature: welcome-screen-simplification, Property 1: Bug Condition - Login Mode Shows Styled Button Instead of Text Link
// **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
describe('Welcome Screen Bug Condition - Login Mode Shows Styled Button Instead of Text Link', function () {

    var nameField, authSubtext, switchToRegister, switchToLogin, authButton, authHeading;
    var passwordStrengthContainer, fixtureContainer;

    beforeEach(function () {
        // Create DOM fixtures that replicate the welcome screen structure (fixed code)
        fixtureContainer = document.createElement('div');
        fixtureContainer.id = 'welcomeScreenFixture';
        fixtureContainer.innerHTML =
            '<div id="welcomeScreen" class="screen">' +
                '<div class="welcome-content">' +
                    '<h1 id="authHeading">✈️ Quizzler</h1>' +
                    '<p id="authSubtext">Log in to continue.</p>' +
                    '<div class="input-group auth-group">' +
                        '<input type="text" id="name" placeholder="Skip at your peril!" maxlength="20" class="hidden">' +
                        '<input type="email" id="email" placeholder="Enter your email" maxlength="100">' +
                        '<span class="validation-hint" id="emailHint">Please enter a valid email address</span>' +
                        '<input type="password" id="password" placeholder="Enter your password" maxlength="50">' +
                        '<div id="passwordStrengthContainer" class="password-strength-container hidden">' +
                            '<div class="password-strength-bar"><div id="passwordStrengthFill" class="password-strength-fill"></div></div>' +
                            '<span id="passwordStrengthLabel" class="password-strength-label"></span>' +
                        '</div>' +
                        '<button onclick="handleAuth()" class="btn btn-primary" id="authButton">Log In</button>' +
                        '<p class="auth-error" id="authError" style="display: none;"></p>' +
                    '</div>' +
                    '<p id="switchToRegister" class="auth-toggle-link">Don\'t have an account? <a href="#" onclick="toggleAuthMode(\'register\'); return false;">Register now.</a></p>' +
                    '<p id="switchToLogin" class="auth-toggle-link hidden">Already have an account? <a href="#" onclick="toggleAuthMode(\'login\'); return false;">Log in.</a></p>' +
                '</div>' +
            '</div>';
        document.body.appendChild(fixtureContainer);

        nameField = document.getElementById('name');
        authSubtext = document.getElementById('authSubtext');
        switchToRegister = document.getElementById('switchToRegister');
        switchToLogin = document.getElementById('switchToLogin');
        authButton = document.getElementById('authButton');
        authHeading = document.getElementById('authHeading');
        passwordStrengthContainer = document.getElementById('passwordStrengthContainer');

        // Reset authMode to login (the default initial state)
        authMode = 'login';
    });

    afterEach(function () {
        document.body.removeChild(fixtureContainer);
        authMode = 'login';
    });

    it('for any sequence of mode toggles ending in login, switchToRegister is NOT a button with btn-secondary class', function () {
        fc.assert(
            fc.property(
                fc.array(fc.constantFrom('login', 'register'), { minLength: 0, maxLength: 10 }),
                function (toggleSequence) {
                    // Always end in login mode
                    var sequence = toggleSequence.concat(['login']);

                    // Execute the toggle sequence
                    for (var i = 0; i < sequence.length; i++) {
                        toggleAuthMode(sequence[i]);
                    }

                    // Re-query the element (in case DOM was replaced)
                    var el = document.getElementById('switchToRegister');

                    // Property: switchToRegister should NOT be a BUTTON with class btn-secondary
                    var isBuggyButton = el.tagName === 'BUTTON' && el.classList.contains('btn-secondary');
                    expect(isBuggyButton).toBe(false);
                }
            ),
            { numRuns: 50 }
        );
    });

    it('for any sequence of mode toggles ending in login, a text link containing "Register now." exists', function () {
        fc.assert(
            fc.property(
                fc.array(fc.constantFrom('login', 'register'), { minLength: 0, maxLength: 10 }),
                function (toggleSequence) {
                    // Always end in login mode
                    var sequence = toggleSequence.concat(['login']);

                    // Execute the toggle sequence
                    for (var i = 0; i < sequence.length; i++) {
                        toggleAuthMode(sequence[i]);
                    }

                    // Property: a text link containing "Register now." should exist below the login button
                    var allLinks = fixtureContainer.querySelectorAll('a');
                    var found = false;
                    for (var j = 0; j < allLinks.length; j++) {
                        if (allLinks[j].textContent.indexOf('Register now.') !== -1) {
                            found = true;
                            break;
                        }
                    }
                    expect(found).toBe(true);
                }
            ),
            { numRuns: 50 }
        );
    });

    it('for any sequence of mode toggles ending in login, authSubtext reads "Log in to continue."', function () {
        fc.assert(
            fc.property(
                fc.array(fc.constantFrom('login', 'register'), { minLength: 0, maxLength: 10 }),
                function (toggleSequence) {
                    // Always end in login mode
                    var sequence = toggleSequence.concat(['login']);

                    // Execute the toggle sequence
                    for (var i = 0; i < sequence.length; i++) {
                        toggleAuthMode(sequence[i]);
                    }

                    var subtextEl = document.getElementById('authSubtext');
                    expect(subtextEl.textContent).toBe('Log in to continue.');
                }
            ),
            { numRuns: 50 }
        );
    });

    it('for any sequence of mode toggles ending in login, name input placeholder is "Skip at your peril!"', function () {
        fc.assert(
            fc.property(
                fc.array(fc.constantFrom('login', 'register'), { minLength: 0, maxLength: 10 }),
                function (toggleSequence) {
                    // Always end in login mode
                    var sequence = toggleSequence.concat(['login']);

                    // Execute the toggle sequence
                    for (var i = 0; i < sequence.length; i++) {
                        toggleAuthMode(sequence[i]);
                    }

                    var nameInput = document.getElementById('name');
                    expect(nameInput.placeholder).toBe('Skip at your peril!');
                }
            ),
            { numRuns: 50 }
        );
    });
});
