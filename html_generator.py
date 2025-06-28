# html_generator.py

import json
import os
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

                options_html += f"""
                <label class="inline-flex items-center px-4 py-2 rounded-full cursor-pointer text-sm font-medium transition duration-200 ease-in-out bg-white text-gray-700 border border-gray-300 hover:bg-gray-100 {option_class}">
                    <input type="radio" name="{field_name}" value="{option}" class="hidden" {field_required_attr}>
                    <span class="ml-2">{option}</span>
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
        
        <!-- Favicon for CliniContact -->
        <link rel="icon" href="{backend_base_url}/static/images/favicon.png" type="image/png"> 

        <!-- Tailwind CSS CDN -->
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
            /* Custom styles for radio buttons to appear colored */
            label.option-yes input[type="radio"]:checked + span {{
                background-color: #22C55E; /* Green for Yes */
                border-color: #22C55E;
                color: white;
            }}
            label.option-no input[type="radio"]:checked + span {{
                background-color: #EF4444; /* Red for No */
                border-color: #EF4444;
                color: white;
            }}
            /* General styling for checked radios if not Yes/No */
            input[type="radio"]:checked + span {{
                background-color: #3B82F6; /* Default blue for checked */
                border-color: #3B82F6;
                color: white;
            }}
            /* Style the hidden radio input's sibling span for visual representation */
            label input[type="radio"] + span {{
                padding: 0.5rem 1rem;
                border: 1px solid #ccc;
                border-radius: 20px;
                background: #fff;
                cursor: pointer;
                transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
                display: inline-block;
            }}
            label input[type="radio"]:hover + span {{
                background-color: #f3f4f6;
            }}
            /* Style for error borders */
            input.border-red-500, select.border-red-500, textarea.border-red-500 {{
                border-color: #EF4444 !important;
            }}
            /* Hide default radio buttons */
            input[type="radio"].hidden {{
                position: absolute;
                opacity: 0;
                width: 0;
                height: 0;
            }}
        </style>
    </head>
    <body class="bg-gray-50 flex items-center justify-center min-h-screen p-4">
        <div class="bg-white p-8 rounded-xl shadow-2xl w-full max-w-lg">
            <!-- CliniContact Logo -->
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

            <form id="qualificationForm">
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

            <!-- Privacy Policy Link -->
            <div class="text-center mt-6 text-sm text-gray-500">
                <p>By submitting this form, you agree to our <a href="https://www.clinicontact.com/privacy-policy" target="_blank" class="text-blue-600 hover:underline">Privacy Policy</a>.</p>
            </div>
        </div>

        <script>
            // Pass study_config data from Python to JavaScript
            const study_config_js = {json.dumps(study_config)};

            const BASE_URL = "{backend_base_url}";
            if (!BASE_URL) console.error("RENDER_EXTERNAL_URL environment variable not set!");

            // FIX: Double-escape backslashes in regexes for JavaScript string literal
            const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\.[a-zA-Z]{{2,}}$/;
            const PHONE_REGEX = /^\\(?([0-9]{{3}})\\)?[-. ]?([0-9]{{3}})[-. ]?([0-9]{{4}})$/;

            // DOM Elements
            const qualificationForm = document.getElementById('qualificationForm');
            const submitButton = document.getElementById('submitButton');
            const generalErrorDiv = document.getElementById('generalError');
            const generalErrorMessageSpan = document.getElementById('generalErrorMessage');
            const smsVerifySection = document.getElementById('smsVerifySection');
            const smsVerifyMessageP = document.getElementById('smsVerifyMessage');
            const smsCodeInput = document.getElementById('smsCodeInput');
            const smsCodeErrorP = document.getElementById('smsCodeError');
            const verifyCodeButton = document.getElementById('verifyCodeButton');
            const resultSection = document.getElementById('resultSection');
            const resultMessageP = document.getElementById('resultMessage');
            const startNewButton = document.getElementById('startNewButton');

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
                            // FIX: Use min_age from study_config_js
                            else if (age < study_config_js.QUALIFICATION_CRITERIA.min_age) error = `You must be ${{study_config_js.QUALIFICATION_CRITERIA.min_age}} or older to participate.`;
                        }}
                        break;
                    default:
                        if (fieldConfig.required && !value.trim()) error = `${{fieldConfig.label}} is required.`;
                        break;
                }}
                return error;
            }}

            document.addEventListener('DOMContentLoaded', function() {{
                const form = document.getElementById('qualificationForm');
                const fields = study_config_js.FORM_FIELDS; // Use study_config_js here

                fields.forEach(field => {{
                    const inputElement = form.elements[field.name];
                    if (inputElement) {{
                        if (field.validation) {{
                            const errorDiv = document.getElementById(`${{field.name}}Error`);
                            const validateAndShowError = () => {{
                                const error = validateField(field.name, inputElement.value, field);
                                if (errorDiv) errorDiv.textContent = error;
                                inputElement.classList.toggle('border-red-500', !!error);
                                inputElement.classList.toggle('border-gray-300', !error);
                            }};
                            inputElement.addEventListener('blur', validateAndShowError);
                            inputElement.addEventListener('input', validateAndShowError);
                        }}

                        if (field.conditional_on) {{
                            const controllingField = form.elements[field.conditional_on.field];
                            const targetElement = document.getElementById(`field-${{field.name}}-container`);
                            if (controllingField && targetElement) {{
                                const updateVisibility = () => {{
                                    const isVisible = controllingField.value === field.conditional_on.value;
                                    targetElement.style.display = isVisible ? 'block' : 'none';
                                    if (!isVisible) {{
                                        if (inputElement.type === 'radio') {{
                                            Array.from(form.elements[field.name]).forEach(radio => radio.checked = false);
                                        }} else {{
                                            inputElement.value = '';
                                        }}
                                    }}
                                }};
                                if (controllingField.type === 'radio') {{
                                    Array.from(form.elements[field.conditional_on.field]).forEach(radio => {{
                                        radio.addEventListener('change', updateVisibility);
                                    }});
                                }} else {{
                                    controllingField.addEventListener('change', updateVisibility);
                                }}
                                updateVisibility();
                            }}
                        }}
                    }}
                }});
            }});

            qualificationForm.addEventListener('submit', async function(event) {{
                event.preventDefault();
                generalErrorDiv.classList.add('hidden');
                generalErrorMessageSpan.textContent = '';

                const formData = new FormData(qualificationForm);
                const data = {{}};
                for (let [key, value] of formData.entries()) {{
                    data[key] = value;
                }}

                data.study_id = qualificationForm.elements['study_id'].value;

                let allFieldsValid = true;
                const fieldsForValidation = study_config_js.FORM_FIELDS; // Use study_config_js here
                fieldsForValidation.forEach(field => {{
                    const inputElement = qualificationForm.elements[field.name];
                    const container = document.getElementById(`field-${{field.name}}-container`);
                    const isVisible = !container || container.style.display !== 'none';

                    if (isVisible) {{
                        const value = data[field.name];
                        const error = validateField(field.name, value, field);
                        const errorDiv = document.getElementById(`${{field.name}}Error`);
                        if (errorDiv) errorDiv.textContent = error;
                        if (inputElement) {{
                            inputElement.classList.toggle('border-red-500', !!error);
                            inputElement.classList.toggle('border-gray-300', !error);
                        }}
                        if (error) allFieldsValid = false;
                    }}
                }});

                if (!allFieldsValid) {{
                    generalErrorDiv.classList.remove('hidden');
                    generalErrorMessageSpan.textContent = 'Please correct the errors in the form.';
                    return;
                }}

                submitButton.disabled = true;
                submitButton.textContent = 'Submitting...';

                try {{
                    const response = await fetch(`${{BASE_URL}}/qualify_form`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify(data),
                    }});
                    const result = await response.json();
                    console.log('Form submission result:', result);

                    if (result.status === 'sms_required') {{
                        currentSubmissionId = result.submission_id;
                        smsVerifyMessageP.textContent = result.message;
                        qualificationForm.classList.add('hidden');
                        smsVerifySection.classList.remove('hidden');
                    }} else if (result.status === 'qualified' || result.status === 'disqualified_no_capture' || result.status === 'duplicate') {{
                        resultMessageP.textContent = result.message;
                        qualificationForm.classList.add('hidden');
                        smsVerifySection.classList.add('hidden');
                        resultSection.classList.remove('hidden');
                    }} else if (result.status === 'error') {{
                        generalErrorDiv.classList.remove('hidden');
                        generalErrorMessageSpan.textContent = result.message;
                    }} else {{
                        generalErrorDiv.classList.remove('hidden');
                        generalErrorMessageSpan.textContent = 'An unexpected response was received.';
                    }}
                }} catch (err) {{
                    console.error('Error submitting form:', err);
                    generalErrorDiv.classList.remove('hidden');
                    generalErrorMessageSpan.textContent = 'A network error occurred. Please try again.';
                }} finally {{
                    submitButton.disabled = false;
                    submitButton.textContent = 'Submit Qualification';
                }}
            }});

            verifyCodeButton.addEventListener('click', async function() {{
                smsCodeErrorP.textContent = '';
                const code = smsCodeInput.value.trim();
                if (!code || code.length !== 4) {{
                    smsCodeErrorP.textContent = 'Please enter a 4-digit code.';
                    return;
                }}

                verifyCodeButton.disabled = true;
                verifyCodeButton.textContent = 'Verifying...';

                try {{
                    const response = await fetch(`${{BASE_URL}}/verify_code`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ submission_id: currentSubmissionId, code: code }}),
                    }});
                    const result = await response.json();
                    console.log('SMS verification result:', result);

                    if (result.status === 'success') {{
                        resultMessageP.textContent = result.message;
                        smsVerifySection.classList.add('hidden');
                        resultSection.classList.remove('hidden');
                    }} else if (result.status === 'invalid_code') {{
                        smsCodeErrorP.textContent = result.message;
                    }} else if (result.status === 'error') {{
                        smsCodeErrorP.textContent = result.message;
                    }} else {{
                        smsCodeErrorP.textContent = 'An unexpected response was received.';
                    }}
                }} catch (err) {{
                    console.error('Error verifying SMS:', err);
                    smsCodeErrorP.textContent = 'A network error occurred during verification. Please try again.';
                }} finally {{
                    verifyCodeButton.disabled = false;
                    verifyCodeButton.textContent = 'Verify Code';
                }}
            }});

            startNewButton.addEventListener('click', function() {{
                qualificationForm.reset();
                generalErrorDiv.classList.add('hidden');
                generalErrorMessageSpan.textContent = '';
                smsCodeInput.value = '';
                smsCodeErrorP.textContent = '';
                currentSubmissionId = null;
                
                qualificationForm.classList.remove('hidden');
                smsVerifySection.classList.add('hidden');
                resultSection.classList.add('hidden');

                const fields = study_config_js.FORM_FIELDS; // Use study_config_js here
                fields.forEach(field => {{
                    if (field.conditional_on) {{
                        const inputElement = qualificationForm.elements[field.name];
                        const container = document.getElementById(`field-${{field.name}}-container`);
                        if (container) {{
                            container.style.display = 'none';
                            if (inputElement) {{
                                if (inputElement.type === 'radio') {{
                                    Array.from(qualificationForm.elements[field.name]).forEach(radio => radio.checked = false);
                                }} else {{
                                    inputElement.value = '';
                                }}
                            }}
                        }}
                    }}
                    const errorDiv = document.getElementById(`${{field.name}}Error`);
                    if (errorDiv) errorDiv.textContent = '';
                    const inputElement = qualificationForm.elements[field.name];
                    if (inputElement) {{
                        inputElement.classList.remove('border-red-500');
                        inputElement.classList.add('border-gray-300');
                    }}
                }});
            }});
        </script>
    </body>
    </html>
    """
    return html_template