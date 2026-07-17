// Feature: welcome-screen-simplification, Property 2: Preservation - Authentication Flow and Registration Mode Behavior Unchanged
// **Validates: Requirements 3.1, 3.2, 3.5, 3.6**
describe('Welcome Screen Preservation - Authentication Flow and Registration Mode Unchanged', function () {

    var authSubtext, switchToRegister, switchToLogin, authButton, authHeading;
    var passwordStrengthContainer, fixtureContainer, emailInput, passwordInput, authError;
    var initialHeadingText;

    beforeEach(function () {
        // Create DOM fixtures that replicate the welcome screen structure (unfixed code)
        fixtureContainer = document.createElement('div');
        fixtureContainer.id = 'welcomeScreenPreservationFixture';
        fixtureContainer.innerHTML =
            '<div id="welcomeScreen" class="screen">' +
                '<div class="welcome-content">' +
                    '<h1 id="authHeading">Quizzler</h1>' +
                    '<p id="authSubtext">Log in or create an account to continue.</p>' +
                    '<div class="input-group auth-group">' +
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
                    '<div class="button-group auth-toggle-group">' +
                        '<button onclick="toggleAuthMode(\'register\')" class="btn btn-secondary" id="switchToRegister">Create an account</button>' +
                        '<button onclick="toggleAuthMode(\'login\')" class="btn btn-secondary hidden" id="switchToLogin">Already have an account?</button>' +
                    '</div>' +
                '</div>' +
            '</div>';
        document.body.appendChild(fixtureContainer);

        authSubtext = document.getElementById('authSubtext');
        switchToRegister = document.getElementById('switchToRegister');
        switchToLogin = document.getElementById('switchToLogin');
        authButton = document.getElementById('authButton');
        authHeading = document.getElementById('authHeading');
        initialHeadingText = authHeading.textContent;
        passwordStrengthContainer = document.getElementById('passwordStrengthContainer');
        emailInput = document.getElementById('email');
        passwordInput = document.getElementById('password');
        authError = document.getElementById('authError');

        // Reset authMode to login (the default initial state)
        authMode = 'login';
    });

    afterEach(function () {
        document.body.removeChild(fixtureContainer);
        authMode = 'login';
    });

    // Property-based test: for any sequence of toggleAuthMode calls, after calling toggleAuthMode('register')
    // the register mode UI state is correct
    describe('Property: Register mode UI state after any toggle sequence', function () {

        it('for any sequence of toggleAuthMode calls ending in register, button says "Create Account", and the heading remains stable', function () {
            fc.assert(
                fc.property(
                    fc.array(fc.constantFrom('login', 'register'), { minLength: 0, maxLength: 10 }),
                    function (toggleSequence) {
                        // Always end in register mode
                        var sequence = toggleSequence.concat(['register']);

                        // Execute the toggle sequence
                        for (var i = 0; i < sequence.length; i++) {
                            toggleAuthMode(sequence[i]);
                        }

                        // Assertions for register mode
                        var ab = document.getElementById('authButton');
                        var ah = document.getElementById('authHeading');
                        var as = document.getElementById('authSubtext');

                        // Name field should not exist
                        expect(document.getElementById('name')).toBe(null);
                        // authButton text is "Create Account"
                        expect(ab.textContent).toBe('Create Account');
                        // authHeading remains the same regardless of auth mode
                        expect(ah.textContent).toBe(initialHeadingText);
                        // authSubtext text is "Register and start the quiz."
                        expect(as.textContent).toBe('Register and start the quiz.');
                    }
                ),
                { numRuns: 50 }
            );
        });
    });

    // Property-based test: for any sequence of toggleAuthMode calls ending in 'login'
    // the login mode UI state is correct
    describe('Property: Login mode UI state after any toggle sequence', function () {

        it('for any sequence of toggleAuthMode calls ending in login, button says "Log In", the heading remains stable, and passwordStrengthContainer is hidden', function () {
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

                        // Assertions for login mode
                        var ab = document.getElementById('authButton');
                        var ah = document.getElementById('authHeading');
                        var psc = document.getElementById('passwordStrengthContainer');

                        // Name field should not exist
                        expect(document.getElementById('name')).toBe(null);
                        // authButton text is "Log In"
                        expect(ab.textContent).toBe('Log In');
                        // authHeading remains the same regardless of auth mode
                        expect(ah.textContent).toBe(initialHeadingText);
                        // passwordStrengthContainer has class hidden
                        expect(psc.classList.contains('hidden')).toBe(true);
                    }
                ),
                { numRuns: 50 }
            );
        });
    });

    // Unit test: handleAuth() with empty email shows error message
    describe('Error handling preservation', function () {

        it('handleAuth() with empty email shows "Please fill in all required fields." error', function (done) {
            // Set up login mode with empty fields
            authMode = 'login';
            emailInput.value = '';
            passwordInput.value = '';

            // Stub fetch to prevent real API calls
            spyOn(window, 'fetch').and.callFake(function () {
                return Promise.resolve(new Response(JSON.stringify({})));
            });

            handleAuth();

            // handleAuth is async but returns early for validation
            setTimeout(function () {
                var errorEl = document.getElementById('authError');
                expect(errorEl.textContent).toBe('Please fill in all required fields.');
                expect(errorEl.style.display).toBe('block');
                done();
            }, 10);
        });

        it('handleAuth() in register mode with short password shows "Password must be at least 8 characters."', function (done) {
            // Set up register mode
            authMode = 'register';
            toggleAuthMode('register');
            emailInput.value = 'test@example.com';
            passwordInput.value = 'short';

            // Add touched class to email to pass validity check
            emailInput.classList.add('touched');

            // Stub fetch to prevent real API calls
            spyOn(window, 'fetch').and.callFake(function () {
                return Promise.resolve(new Response(JSON.stringify({})));
            });

            handleAuth();

            setTimeout(function () {
                var errorEl = document.getElementById('authError');
                expect(errorEl.textContent).toBe('Password must be at least 8 characters.');
                expect(errorEl.style.display).toBe('block');
                done();
            }, 10);
        });
    });

    // Unit test: toggling to register mode and back preserves form field values
    describe('Form field value preservation across mode toggles', function () {

        it('toggling to register mode and back preserves email and password values', function () {
            // Enter values in login mode
            emailInput.value = 'user@test.com';
            passwordInput.value = 'mypassword123';

            // Toggle to register mode
            toggleAuthMode('register');

            // Values should still be there
            expect(emailInput.value).toBe('user@test.com');
            expect(passwordInput.value).toBe('mypassword123');

            // Toggle back to login
            toggleAuthMode('login');

            // Email and password should still be preserved
            expect(emailInput.value).toBe('user@test.com');
            expect(passwordInput.value).toBe('mypassword123');
        });
    });
});
