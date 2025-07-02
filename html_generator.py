# html_generator.py

import json
import os
import re # Import re for regex escaping
from typing import Dict, Any

def generate_html_form(study_config: Dict[str, Any], study_id: str) -> str:
    """
    Generates the full HTML content for a dynamic qualification form based on study configuration.
    Includes embedded CSS and client-side JavaScript for validation and submission.
    Incorporates CliniContact branding (logo, favicon, privacy policy).
    """
    form_fields_html = ""
    for field in study_config["FORM_FIELDS"]:
        field_name = field["name"]
        field_label = field["label"]
        field_type = field["type"]
        field_placeholder = field.get("placeholder", "")
        field_required_attr = "required" if field.get("required", False) else ""
        field_description = field.get("description", "")
        field_validation_type = field.get("validation", "") # For JS validation hints

        # Conditional display logic for JS (initially hidden if conditional_on exists)
        conditional_display_style = ""
        conditional_data_attrs = ""
        if "conditional_on" in field:
            conditional_display_style = "display: none;" # Initially hidden
            # Store conditional info directly on the container for easier JS access
            conditional_data_attrs = f'data-conditional-field="{field["conditional_on"]["field"]}" data-conditional-value="{field["conditional_on"]["value"]}"'

        if field_type == "text" or field_type == "email" or field_type == "tel":
            form_fields_html += f"""
            <div class="mb-4" id="field-{field_name}-container" style="{conditional_display_style}" {conditional_data_attrs}>
                <label for="{field_name}" class="block text-gray-700 text-sm font-bold mb-2">{field_label}</label>
                <input type="{field_type}" id="{field_name}" name="{field_name}" placeholder="{field_placeholder}" {field_required_attr}
                       data-validation-type="{field_validation_type}"
                       class="shadow appearance-none border border-gray-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:shadow-outline transition duration-200 ease-in-out">
                <p class="text-gray-500 text-xs mt-1">{field_description}</p>
                <div id="{field_name}Error" class="text-red-500 text-xs mt-1"></div>
            </div>
            """
        elif field_type == "radio":
            options_html = ""
            for option in field.get("options", []):
                option_class = ""
                if option.lower() == "yes":
                    option_class = "option-yes"
                elif option.lower() == "no":
                    option_class = "option-no"

                # FIX 2: Ensure the span is the immediate sibling and the label wraps both
                # Use a unique ID for each radio option for better accessibility and targeting
                options_html += f"""
                <label class="inline-flex items-center cursor-pointer mr-4">
                    <input type="radio" name="{field_name}" value="{option}" class="hidden-radio" id="{field_name}-{option.lower()}" {field_required_attr}>
                    <span class="px-4 py-2 rounded-full text-sm font-medium transition duration-200 ease-in-out bg-white text-gray-700 border border-gray-300 hover:bg-gray-100 {option_class}">
                        {option}
                    </span>
                </label>
                """
            form_fields_html += f"""
            <div class="mb-4" id="field-{field_name}-container" style="{conditional_display_style}" {conditional_data_attrs}>
                <label class="block text-gray-700 text-sm font-bold mb-2">{field_label}</label>
                <div class="flex flex-wrap gap-2 mt-1">
                    {options_html}
                </div>
                <p class="text-gray-500 text-xs mt-1">{field_description}</p>
                <div id="{field_name}Error" class="text-red-500 text-xs mt-1"></div>
            </div>
            """

    backend_base_url = os.getenv('RENDER_EXTERNAL_URL')
    if not backend_base_url:
        print("WARNING: RENDER_EXTERNAL_URL environment variable not set. Using a placeholder for local testing.")
        backend_base_url = "http://localhost:8000"

    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{study_config.get("FORM_TITLE", "Qualification Form")}</title>
        
        <link rel="icon" href="{backend_base_url}/static/images/favicon.png" type="image/png"> 

        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            /* Basic fade-in animation */
            @keyframes fadeIn {{
                from {{ opacity: 0; }}
                to {{ opacity: 1; }}
            }}
            .fade-in {{
                animation: fadeIn 0.5s ease-in-out;
            }}
            /* Hide default radio buttons */
            .hidden-radio {{
                position: absolute;
                opacity: 0;
                width: 1px;
                height: 1px;
                padding: 0;
                margin: -1px;
                overflow: hidden;
                clip: rect(0, 0, 0, 0);
                white-space: nowrap;
                border-width: 0;
                pointer-events: none; /* Ensure no interaction with hidden element */
            }}
            /* Custom styles for radio buttons to appear colored */
            label input[type="radio"].hidden-radio:checked + span {{
                background-color: #3B82F6; /* Default blue for checked */
                border-color: #3B82F6;
                color: white;
            }}
            label.option-yes input[type="radio"].hidden-radio:checked + span {{
                background-color: #22C55E; /* Green for Yes */
                border-color: #22C55E;
            }}
            label.option-no input[type="radio"].hidden-radio:checked + span {{
                background-color: #EF4444; /* Red for No */
                border-color: #EF4444;
            }}
            /* Style the visible span for radio buttons */
            label span {{
                padding: 0.5rem 1rem;
                border: 1px solid #ccc;
                border-radius: 20px;
                background: #fff;
                cursor: pointer;
                transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
                display: inline-block;
                user-select: none; /* Prevent text selection */
            }}
            label span:hover {{
                background-color: #f3f4f6;
            }}
            /* Style for error borders */
            input.border-red-500, select.border-red-500, textarea.border-red-500 {{
                border-color: #EF4444 !important;
            }}
        </style>
    </head>
    <body class="bg-gray-50 flex items-center justify-center min-h-screen p-4">
        <div class="bg-white p-8 rounded-xl shadow-2xl w-full max-w-lg">
            <div class="text-center mb-6">
                <img src="{backend_base_url}/static/images/clini-logo.png" alt="CliniContact Logo" class="mx-auto h-16 mb-4"> 
            </div>

            <h2 class="text-3xl font-extrabold text-gray-900 text-center mb-6">
                {study_config.get("FORM_TITLE", "Qualify for Studies")}
            </h2>

            <div id="generalError" class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg relative mb-6 hidden" role="alert">
                <strong class="font-bold">Error:</strong>
                <span id="generalErrorMessage" class="block sm:inline ml-2"></span>
            </div>

            <form id="qualificationForm" method="POST">
                <input type="hidden" name="study_id" value="{study_id}">
                {form_fields_html}
                
                <button type="submit" id="submitButton" class="w-full py-3 px-4 rounded-lg text-white font-semibold transition duration-300 ease-in-out bg-blue-600 hover:bg-blue-700 shadow-lg">
                    Submit Qualification
                </button>
            </form>

            <div id="smsVerifySection" class="text-center fade-in hidden">
                <p id="smsVerifyMessage" class="text-gray-800 text-lg mb-4"></p>
                <p class="text-gray-600 text-sm mb-6">Please enter the 4-digit code sent to your phone.</p>
                <input type="text" id="smsCodeInput" placeholder="4-digit code" maxlength="4"
                       class="shadow appearance-none border border-gray-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:shadow-outline text-center text-xl tracking-widest transition duration-200 ease-in-out">
                <p id="smsCodeError" class="text-red-500 text-xs mt-2"></p>
                <button type="button" id="verifyCodeButton" class="w-full mt-6 py-3 px-4 rounded-lg text-white font-semibold transition duration-300 ease-in-out bg-green-600 hover:bg-green-700 shadow-lg">
                    Verify Code
                </button>
            </div>

            <div id="resultSection" class="text-center fade-in hidden">
                <p id="resultMessage" class="text-gray-800 text-lg mb-6"></p>
                <button type="button" id="startNewButton" class="w-full py-3 px-4 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 transition duration-300 ease-in-out shadow-lg">
                    Start New Qualification
                </button>
            </div>

            <div class="text-center mt-6 text-sm text-gray-500">
                <p>By submitting this form, you agree to our <a href="https://www.clinicontact.com/privacy-policy" target="_blank" class="text-blue-600 hover:underline">Privacy Policy</a>.</p>
            </div>
        </div>

        <script>
            // Pass study_config data from Python to JavaScript
            const study_config_js = {json.dumps(study_config)};

            const BASE_URL = "{backend_base_url}";
            if (!BASE_URL) console.error("RENDER_EXTERNAL_URL environment variable not set!");

            // Correctly escape backslashes in regexes for JavaScript string literal
            const EMAIL_REGEX = new RegExp("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\.[a-zA-Z]{{2,}}$");
            const PHONE_REGEX = new RegExp("^[+]?1?[-. ]?\\\\(?\\\\d{{3}}\\\\)?[-. ]?\\\\d{{3}}[-. ]?\\\\d{{4}}$");

            // DOM Elements (declared as variables to be assigned inside DOMContentLoaded)
            let qualificationForm;
            let submitButton;
            let generalErrorDiv;
            let generalErrorMessageSpan;
            let smsVerifySection;
            let smsVerifyMessageP;
            let smsCodeInput;
            let smsCodeErrorP;
            let verifyCodeButton;
            let resultSection;
            let resultMessageP;
            let startNewButton;

            let currentSubmissionId = null;

            function calculateAge(dobString) {{
                if (!dobString) return null;
                const parts = dobString.split('/');
                if (parts.length !== 3) return null;
                const month = parseInt(parts[0], 10);
                const day = parseInt(parts[1], 10);
                const year = parseInt(parts[2], 10);

                if (isNaN(month) || isNaN(day) || isNaN(year) || month < 1 || month > 12 || day < 1 || day > 31 || year < 1900) {{
                    return null;
                }}

                const birthDate = new Date(year, month - 1, day);
                const today = new Date();

                let age = today.getFullYear() - birthDate.getFullYear();
                const m = today.getMonth() - birthDate.getMonth();
                if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {{
                    age--;
                }}
                return age;
            }}

            function validateField(name, value, fieldConfig) {{
                let error = '';
                switch (fieldConfig.validation) {{
                    case 'email':
                        if (!value.trim()) error = fieldConfig.required ? 'Email is required.' : '';
                        else if (!EMAIL_REGEX.test(value)) error = 'Invalid email format.';
                        break;
                    case 'phone':
                        if (!value.trim()) error = fieldConfig.required ? 'Phone number is required.' : '';
                        else if (!PHONE_REGEX.test(value)) error = 'Invalid US phone number (e.g., 5551234567).';
                        break;
                    case 'dob_age':
                        if (!value.trim()) error = fieldConfig.required ? 'Date of birth is required.' : '';
                        else {{
                            const age = calculateAge(value);
                            if (age === null) error = 'Invalid date format (MM/DD/YYYY).';
                            else {{
                                const ageRule = study_config_js.QUALIFICATION_RULES.find(rule => rule.type === 'age' && rule.operator === 'greater_than_or_equal');
                                if (ageRule && age < ageRule.value) {{
                                    error = `You must be ${{ageRule.value}} or older to participate.`;
                                }}
                            }}
                        }}
                        break;                        
                    default:
                        if (fieldConfig.required && !value.trim()) error = `${{fieldConfig.label}} is required.`;
                        break;
                }}
                if (error) {{
                    console.error(`Validation Error for ${{name}}: ${{error}}`);
                }}
                return error;
            }}

            document.addEventListener('DOMContentLoaded', function() {{
                console.log('DOM Content Loaded. Initializing form elements...');
                qualificationForm = document.getElementById('qualificationForm');
                submitButton = document.getElementById('submitButton');
                generalErrorDiv = document.getElementById('generalError');
                generalErrorMessageSpan = document.getElementById('generalErrorMessage');
                smsVerifySection = document.getElementById('smsVerifySection');
                smsVerifyMessageP = document.getElementById('smsVerifyMessage');
                smsCodeInput = document.getElementById('smsCodeInput');
                smsCodeErrorP = document.getElementById('smsCodeError');
                verifyCodeButton = document.getElementById('verifyCodeButton');
                resultSection = document.getElementById('resultSection');
                resultMessageP = document.getElementById('resultMessage');
                startNewButton = document.getElementById('startNewButton');

                const fields = study_config_js.FORM_FIELDS;

                fields.forEach(field => {{
                    const inputElement = qualificationForm.elements[field.name];
                    const container = document.getElementById(`field-${{field.name}}-container`);
                    
                    console.log(`Processing field: ${{field.name}}`);
                    console.log(`  inputElement:`, inputElement);
                    console.log(`  container:`, container);

                    if (inputElement && container) {{
                        if (field.validation) {{
                            const errorDiv = document.getElementById(`${{field.name}}Error`);
                            const validateAndShowError = () => {{
                                const error = validateField(field.name, inputElement.value, field);
                                if (errorDiv) errorDiv.textContent = error;
                                if (inputElement.nodeType === Node.ELEMENT_NODE) {{
                                    inputElement.classList.toggle('border-red-500', !!error);
                                    inputElement.classList.toggle('border-gray-300', !error);
                                }} else if (inputElement.length && inputElement[0].type === 'radio') {{
                                    container.classList.toggle('border-red-500', !!error);
                                    container.classList.toggle('border-gray-300', !error);
                                }}
                            }};
                            if (inputElement.nodeType === Node.ELEMENT_NODE) {{
                                inputElement.addEventListener('blur', validateAndShowError);
                                inputElement.addEventListener('input', validateAndShowError);
                            }}
                            if (inputElement.length && inputElement[0].type === 'radio') {{
                                Array.from(qualificationForm.elements[field.name]).forEach(radio => {{
                                    radio.addEventListener('change', validateAndShowError);
                                }});
                            }}
                        }}

                        if (field.conditional_on) {{
                            const controllingFieldElements = qualificationForm.elements[field.conditional_on.field];
                            if (controllingFieldElements) {{
                                const updateVisibility = () => {{
                                    let controllingValue;
                                    if (controllingFieldElements.length && controllingFieldElements[0].type === 'radio') {{
                                        const checkedRadio = Array.from(controllingFieldElements).find(radio => radio.checked);
                                        controllingValue = checkedRadio ? checkedRadio.value : '';
                                    }} else {{
                                        controllingValue = controllingFieldElements.value;
                                    }}

                                    const isVisible = controllingValue === field.conditional_on.value;
                                    container.style.display = isVisible ? 'block' : 'none';
                                    if (!isVisible) {{
                                        if (inputElement.type === 'radio') {{
                                            Array.from(qualificationForm.elements[field.name]).forEach(radio => radio.checked = false);
                                        }} else if (inputElement.nodeType === Node.ELEMENT_NODE) {{
                                            inputElement.value = '';
                                        }}
                                        const errorDiv = document.getElementById(`${{field.name}}Error`);
                                        if (errorDiv) errorDiv.textContent = '';
                                        if (inputElement.nodeType === Node.ELEMENT_NODE) {{
                                            inputElement.classList.remove('border-red-500');
                                            inputElement.classList.add('border-gray-300');
                                        }}
                                        container.classList.remove('border-red-500');
                                        container.classList.add('border-gray-300');
                                    }}
                                }};
                                if (controllingFieldElements.length && controllingFieldElements[0].type === 'radio') {{
                                    Array.from(controllingFieldElements).forEach(radio => {{
                                        radio.addEventListener('change', updateVisibility);
                                    }});
                                }} else {{
                                    controllingFieldElements.addEventListener('change', updateVisibility);
                                }}
                                updateVisibility();
                            }}
                        }}
                    }}
                }});

                qualificationForm.addEventListener('submit', async function(event) {{
                    console.log('Form submission initiated.');
                    event.preventDefault();
                    console.log('event.preventDefault() called.');
                    generalErrorDiv.classList.add('hidden');
                    generalErrorMessageSpan.textContent = '';
                    
                    const data = {{}};
                    const fieldsInConfig = study_config_js.FORM_FIELDS;

                    let allFieldsValid = true;

                    fieldsInConfig.forEach(field => {{
                        const container = document.getElementById(`field-${{field.name}}-container`);
                        const isVisible = !container || container.style.display !== 'none';

                        if (isVisible) {{
                            let fieldValue;
                            const inputElement = qualificationForm.elements[field.name];

                            if (inputElement && inputElement.length && inputElement[0].type === 'radio') {{
                                const checkedRadio = Array.from(inputElement).find(radio => radio.checked);
                                fieldValue = checkedRadio ? checkedRadio.value : '';
                            }} else if (inputElement && inputElement.nodeType === Node.ELEMENT_NODE) {{
                                fieldValue = inputElement.value;
                            }} else {{
                                fieldValue = '';
                            }}
                            data[field.name] = fieldValue;

                            const error = validateField(field.name, fieldValue, field);
                            const errorDiv = document.getElementById(`${{field.name}}Error`);

                            if (errorDiv) errorDiv.textContent = error;
                            if (inputElement) {{
                                if (inputElement.nodeType === Node.ELEMENT_NODE) {{
                                    inputElement.classList.toggle('border-red-500', !!error);
                                    inputElement.classList.toggle('border-gray-300', !error);
                                }} else if (inputElement.length && inputElement[0].type === 'radio') {{
                                    container.classList.toggle('border-red-500', !!error);
                                    container.classList.toggle('border-gray-300', !error);
                                }}
                            }}
                            if (error) {{
                                allFieldsValid = false;
                            }}
                        }}
                    }});

                    data.study_id = qualificationForm.elements['study_id'].value;

                    if (!allFieldsValid) {{
                        generalErrorDiv.classList.remove('hidden');
                        generalErrorMessageSpan.textContent = 'Please correct the errors in the form.';
                        console.log('Form validation failed. Not submitting.');
                        return;
                    }}

                    console.log('Form validated. Attempting fetch...');
                    submitButton.disabled = true;
                    submitButton.textContent = 'Submitting...';

                    try {{
                        // Set redirect mode to 'manual' to prevent automatic following by fetch
                        const response = await fetch(`${{BASE_URL}}/qualify_form`, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify(data),
                            redirect: 'manual' // Crucial change here
                        }});
                        
                        // Check if the response is a redirect (3xx status code)
                        if (response.status >= 300 && response.status < 400) {{
                            const redirectUrl = response.headers.get('Location');
                            if (redirectUrl) {{
                                console.log('Manual redirect detected. Navigating to:', redirectUrl);
                                window.location.href = redirectUrl; // Manually navigate the browser
                                return; // Stop further JavaScript execution
                            }} else {{
                                console.error('Redirect status received but no Location header found.');
                                generalErrorDiv.classList.remove('hidden');
                                generalErrorMessageSpan.textContent = 'A redirect error occurred. Please try again.';
                            }}
                        }}

                        // If not a redirect, proceed to parse JSON (e.g., for 'sms_required' status)
                        const result = await response.json();
                        console.log('Form submission fetch result:', result);

                        if (result.status === 'sms_required') {{
                            currentSubmissionId = result.submission_id;
                            smsVerifyMessageP.textContent = result.message;
                            qualificationForm.classList.add('hidden');
                            smsVerifySection.classList.remove('hidden');
                            console.log('SMS verification required. Displaying SMS section.');
                        }} else if (result.status === 'qualified' || result.status === 'disqualified_no_capture' || result.status === 'duplicate') {{
                            // This block should theoretically not be reached if the backend correctly sends 303.
                            // It's a fallback for unexpected non-redirecting success responses.
                            resultMessageP.textContent = result.message;
                            qualificationForm.classList.add('hidden');
                            smsVerifySection.classList.add('hidden');
                            resultSection.classList.remove('hidden');
                            console.log('Submission complete. Displaying result section (non-redirect path).');
                        }} else if (result.status === 'error') {{
                            generalErrorDiv.classList.remove('hidden');
                            generalErrorMessageSpan.textContent = result.message;
                            console.error('Submission returned an error:', result.message);
                        }} else {{
                            generalErrorDiv.classList.remove('hidden');
                            generalErrorMessageSpan.textContent = 'An unexpected response was received.';
                            console.error('Submission returned unexpected status:', result.status);
                        }}
                    }} catch (err) {{
                        console.error('Error during form submission fetch:', err);
                        generalErrorDiv.classList.remove('hidden');
                        generalErrorMessageSpan.textContent = 'A network error occurred or an unexpected response was received. Please try again.';
                    }} finally {{
                        submitButton.disabled = false;
                        submitButton.textContent = 'Submit Qualification';
                        console.log('Submission process finished.');
                    }}
                }});

                verifyCodeButton.addEventListener('click', async function() {{
                    console.log('Verify code button clicked.');
                    smsCodeErrorP.textContent = '';
                    generalErrorDiv.classList.add('hidden');
                    generalErrorMessageSpan.textContent = '';

                    const code = smsCodeInput.value.trim();
                    if (!code || code.length !== 4) {{
                        smsCodeErrorP.textContent = 'Please enter a 4-digit code.';
                        return;
                    }}

                    verifyCodeButton.disabled = true;
                    verifyCodeButton.textContent = 'Verifying...';

                    try {{
                        // Set redirect mode to 'manual' to prevent automatic following by fetch
                        const response = await fetch(`${{BASE_URL}}/verify_code`, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ submission_id: currentSubmissionId, code: code }}),
                            redirect: 'manual' // Crucial change here
                        }});
                        
                        // Check if the response is a redirect (3xx status code)
                        if (response.status >= 300 && response.status < 400) {{
                            const redirectUrl = response.headers.get('Location');
                            if (redirectUrl) {{
                                console.log('Manual redirect detected. Navigating to:', redirectUrl);
                                window.location.href = redirectUrl; // Manually navigate the browser
                                return; // Stop further JavaScript execution
                            }} else {{
                                console.error('Redirect status received but no Location header found.');
                                smsCodeErrorP.textContent = 'A redirect error occurred during verification. Please try again.';
                            }}
                        }}

                        // If not a redirect, proceed to parse JSON (e.g., for 'invalid_code' or an error)
                        const result = await response.json();
                        console.log('SMS verification fetch result:', result);

                        if (result.status === 'success') {{
                            // This block should theoretically not be reached if the backend correctly sends 303.
                            // It's a fallback for unexpected non-redirecting success responses.
                            resultMessageP.textContent = result.message;
                            qualificationForm.classList.add('hidden');
                            smsVerifySection.classList.add('hidden');
                            resultSection.classList.remove('hidden');
                            console.log('SMS verification successful (non-redirect path).');
                        }} else if (result.status === 'invalid_code') {{
                            smsCodeErrorP.textContent = result.message;
                            console.log('SMS verification: Invalid code.');
                        }} else if (result.status === 'error') {{
                            smsCodeErrorP.textContent = 'A network error occurred during verification. Please try again.';
                            console.error('SMS verification returned an error:', result.message);
                        }} else {{
                            smsCodeErrorP.textContent = 'An unexpected response was received.';
                            console.error('SMS verification returned unexpected status:', result.status);
                        }}
                    }} catch (err) {{
                        console.error('Error during SMS verification fetch:', err);
                        smsCodeErrorP.textContent = 'A network error occurred or an unexpected response was received during verification. Please try again.';
                        generalErrorDiv.classList.remove('hidden');
                        generalErrorMessageSpan.textContent = 'A network error occurred. Please try again.';
                    }} finally {{
                        verifyCodeButton.disabled = false;
                        verifyCodeButton.textContent = 'Verify Code';
                        console.log('SMS verification process finished.');
                    }}
                }});

                startNewButton.addEventListener('click', function() {{
                    console.log('Start New Qualification button clicked. Resetting form.');
                    qualificationForm.reset();
                    generalErrorDiv.classList.add('hidden');
                    generalErrorMessageSpan.textContent = '';
                    smsCodeInput.value = '';
                    smsCodeErrorP.textContent = '';
                    currentSubmissionId = null;
                    
                    qualificationForm.classList.remove('hidden');
                    smsVerifySection.classList.add('hidden');
                    resultSection.classList.add('hidden');

                    const fields = study_config_js.FORM_FIELDS;
                    fields.forEach(field => {{
                        if (field.conditional_on) {{
                            const inputElement = qualificationForm.elements[field.name];
                            const container = document.getElementById(`field-${{field.name}}-container`);
                            if (container) {{
                                container.style.display = 'none';
                                if (inputElement) {{
                                    if (inputElement.type === 'radio') {{
                                        Array.from(qualificationForm.elements[field.name]).forEach(radio => radio.checked = false);
                                    }} else if (inputElement.nodeType === Node.ELEMENT_NODE) {{
                                        inputElement.value = '';
                                    }}
                                }}
                            }}
                        }}
                        const errorDiv = document.getElementById(`${{field.name}}Error`);
                        if (errorDiv) errorDiv.textContent = '';
                        const inputElement = qualificationForm.elements[field.name];
                        if (inputElement && inputElement.nodeType === Node.ELEMENT_NODE) {{
                            inputElement.classList.remove('border-red-500');
                            inputElement.classList.add('border-gray-300');
                        }}
                        else if (inputElement && inputElement.length && inputElement[0].type === 'radio' && container) {{
                            container.classList.remove('border-red-500');
                            container.classList.add('border-gray-300');
                        }}
                    }});
                }});
            }});
        </script>
    </body>
    </html>
    """
    return html_template