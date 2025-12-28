/**
 * Preset Editor - Manages prompt preset editing interface
 */

(function() {
    'use strict';

    let currentPresetName = null;
    let variableRegistry = {};
    let defaultAssemblyTemplates = null;  // Cached assembly templates from default preset
    const DEFAULT_PRESET_KEY = 'webui_default_preset';

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        initPresetEditor();
    });

    function initPresetEditor() {
        const editorBtn = document.getElementById('preset-editor-btn');
        const modal = document.getElementById('preset-editor-modal');
        const modalHeader = modal ? modal.querySelector('.modal-header') : null;
        const closeBtn = document.getElementById('preset-modal-close');
        const cancelBtn = document.getElementById('cancel-preset-btn');
        const saveBtn = document.getElementById('save-preset-btn');
        const deleteBtn = document.getElementById('delete-preset-btn');
        const createBtn = document.getElementById('create-new-preset-btn');
        const presetSelect = document.getElementById('preset-select');
        const defaultPresetSelect = document.getElementById('default-preset-select');

        if (!editorBtn || !modal) return;

        // Open modal
        editorBtn.addEventListener('click', function(e) {
            e.preventDefault();
            openModal();
        });

        // Close modal - header click
        if (modalHeader) {
            modalHeader.addEventListener('click', closeModal);
        }

        // Close modal - buttons and backdrop
        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        modal.addEventListener('click', function(e) {
            if (e.target === modal) closeModal();
        });

        // Tab switching
        initTabSwitching();

        // Default preset selection
        defaultPresetSelect.addEventListener('change', function() {
            saveDefaultPreset(this.value);
        });

        // Preset selection
        presetSelect.addEventListener('change', function() {
            loadPreset(this.value);
        });

        // Save preset
        saveBtn.addEventListener('click', savePreset);

        // Delete preset
        deleteBtn.addEventListener('click', deletePreset);

        // Create new preset
        createBtn.addEventListener('click', createNewPreset);

        // Listen for storage changes in other tabs for default preset sync
        window.addEventListener('storage', function(e) {
            if (e.key === DEFAULT_PRESET_KEY && e.newValue !== e.oldValue) {
                // Another tab changed the default preset, update our selector
                const defaultPresetSelect = document.getElementById('default-preset-select');
                if (defaultPresetSelect && e.newValue) {
                    defaultPresetSelect.value = e.newValue;
                    console.log('Default preset synced from another tab:', e.newValue);
                }
            }
        });
    }

    function openModal() {
        const modal = document.getElementById('preset-editor-modal');
        modal.classList.add('active');
        loadPresetList();
        loadVariableRegistry();
        loadDefaultAssemblyTemplates();  // Load assembly templates from default preset
    }

    function closeModal() {
        const modal = document.getElementById('preset-editor-modal');
        modal.classList.remove('active');
        currentPresetName = null;
    }

    function initTabSwitching() {
        const tabs = document.querySelectorAll('.preset-tab');
        const panels = document.querySelectorAll('.tab-panel');

        tabs.forEach(tab => {
            tab.addEventListener('click', function() {
                const targetPanel = this.getAttribute('data-tab');

                // Remove active class from all tabs and panels
                tabs.forEach(t => t.classList.remove('active'));
                panels.forEach(p => p.classList.remove('active'));

                // Add active class to clicked tab and corresponding panel
                this.classList.add('active');
                const panel = document.querySelector(`[data-panel="${targetPanel}"]`);
                if (panel) {
                    panel.classList.add('active');
                }
            });
        });
    }

    function loadPresetList() {
        fetch('/api/prompts/presets')
            .then(response => response.json())
            .then(data => {
                const presetSelect = document.getElementById('preset-select');
                const defaultPresetSelect = document.getElementById('default-preset-select');
                const defaultPreset = getDefaultPreset();

                presetSelect.innerHTML = '';
                defaultPresetSelect.innerHTML = '';

                if (data.presets && data.presets.length > 0) {
                    data.presets.forEach(preset => {
                        // Populate edit preset dropdown
                        const option = document.createElement('option');
                        option.value = preset.filename;
                        option.textContent = preset.name;
                        if (preset.filename === defaultPreset) {
                            option.textContent += ' ⭐';
                        }
                        presetSelect.appendChild(option);

                        // Populate default preset dropdown
                        const defaultOption = document.createElement('option');
                        defaultOption.value = preset.filename;
                        defaultOption.textContent = preset.name;
                        defaultPresetSelect.appendChild(defaultOption);
                    });

                    // Set default preset in dropdown
                    defaultPresetSelect.value = defaultPreset;

                    // Load the first preset for editing by default
                    if (data.presets.length > 0) {
                        loadPreset(data.presets[0].filename);
                    }
                } else {
                    presetSelect.innerHTML = '<option value="">No presets available</option>';
                    defaultPresetSelect.innerHTML = '<option value="">No presets available</option>';
                }
            })
            .catch(error => {
                console.error('Error loading preset list:', error);
                WebUIUtils.showError('Failed to load preset list');
            });
    }

    function getDefaultPreset() {
        return localStorage.getItem(DEFAULT_PRESET_KEY) || 'default';
    }

    function saveDefaultPreset(presetName) {
        localStorage.setItem(DEFAULT_PRESET_KEY, presetName);
        WebUIUtils.showSuccess(`Default preset set to "${presetName}"`);
        // Reload preset list to update star indicators
        loadPresetList();
    }

    function loadPreset(presetName) {
        if (!presetName) return;

        currentPresetName = presetName;

        fetch(`/api/prompts/presets/${presetName}`)
            .then(response => response.json())
            .then(data => {
                // Populate metadata
                document.getElementById('preset-name').value = data.preset_metadata.name || '';
                document.getElementById('preset-description').value = data.preset_metadata.description || '';

                // Populate base prompt fields
                document.getElementById('base-schema').value = data.base_prompt.schema || '';
                document.getElementById('base-tools').value = data.base_prompt.tools_description || '';
                document.getElementById('base-domain').value = data.base_prompt.domain_context || '';
                document.getElementById('base-task').value = data.base_prompt.task_instructions || '';

                // Populate verification prompt
                document.getElementById('verification-task').value =
                    data.verification_prompt.verification_task_template || '';

                // Populate continuation prompt
                document.getElementById('continuation-context').value =
                    data.continuation_prompt.iteration_context_template || '';

                // Populate report prompt
                document.getElementById('report-instructions').value =
                    data.report_prompt.report_instructions || '';

                // Highlight placeholders in textareas
                highlightPlaceholders();
            })
            .catch(error => {
                console.error('Error loading preset:', error);
                WebUIUtils.showError('Failed to load preset');
            });
    }

    function savePreset() {
        if (!currentPresetName) {
            WebUIUtils.showError('No preset selected');
            return;
        }

        // Build preset data from form
        const presetData = {
            preset_metadata: {
                name: document.getElementById('preset-name').value,
                description: document.getElementById('preset-description').value,
                version: '1.0',
                created: new Date().toISOString().split('T')[0],
                author: 'WebUI Editor'
            },
            base_prompt: {
                schema: document.getElementById('base-schema').value,
                tools_description: document.getElementById('base-tools').value,
                domain_context: document.getElementById('base-domain').value,
                task_instructions: document.getElementById('base-task').value,
                assembly_template: defaultAssemblyTemplates?.base_prompt || "Database schema:\n{schema}\n\n{tools_description}\n\n{domain_context}\n\n{task_instructions}"
            },
            verification_prompt: {
                verification_task_template: document.getElementById('verification-task').value,
                assembly_template: defaultAssemblyTemplates?.verification_prompt || "{base_prompt}\n\n{memory_summary}\n\n{verification_task_template}"
            },
            continuation_prompt: {
                iteration_context_template: document.getElementById('continuation-context').value,
                assembly_template: defaultAssemblyTemplates?.continuation_prompt || "{base_prompt}{iteration_context_template}"
            },
            report_prompt: {
                report_instructions: document.getElementById('report-instructions').value,
                assembly_template: defaultAssemblyTemplates?.report_prompt || "{report_instructions}"
            },
            variable_registry: variableRegistry
        };

        // Save via API
        fetch(`/api/prompts/presets/${currentPresetName}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(presetData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                WebUIUtils.showSuccess(`Preset "${currentPresetName}" saved successfully`);
            } else {
                WebUIUtils.showError(data.error || 'Failed to save preset');
            }
        })
        .catch(error => {
            console.error('Error saving preset:', error);
            WebUIUtils.showError('Failed to save preset');
        });
    }

    function deletePreset() {
        if (!currentPresetName) {
            WebUIUtils.showError('No preset selected');
            return;
        }

        if (currentPresetName === 'default') {
            WebUIUtils.showError('Cannot delete default preset');
            return;
        }

        if (!confirm(`Are you sure you want to delete preset "${currentPresetName}"?`)) {
            return;
        }

        fetch(`/api/prompts/presets/${currentPresetName}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                WebUIUtils.showSuccess(`Preset "${currentPresetName}" deleted successfully`);
                loadPresetList();
            } else {
                WebUIUtils.showError(data.error || 'Failed to delete preset');
            }
        })
        .catch(error => {
            console.error('Error deleting preset:', error);
            WebUIUtils.showError('Failed to delete preset');
        });
    }

    function createNewPreset() {
        const presetName = prompt('Enter new preset name (without .json extension):');
        if (!presetName) return;

        // Validate preset name
        if (!/^[a-zA-Z0-9_-]+$/.test(presetName)) {
            WebUIUtils.showError('Preset name can only contain letters, numbers, hyphens, and underscores');
            return;
        }

        // Create with default template
        const presetData = {
            preset_metadata: {
                name: presetName,
                description: 'New preset',
                version: '1.0',
                created: new Date().toISOString().split('T')[0],
                author: 'WebUI Editor'
            },
            base_prompt: {
                schema: '',
                tools_description: '',
                domain_context: '',
                task_instructions: '',
                assembly_template: defaultAssemblyTemplates?.base_prompt || "Database schema:\n{schema}\n\n{tools_description}\n\n{domain_context}\n\n{task_instructions}"
            },
            verification_prompt: {
                verification_task_template: '',
                assembly_template: defaultAssemblyTemplates?.verification_prompt || "{base_prompt}\n\n{memory_summary}\n\n{verification_task_template}"
            },
            continuation_prompt: {
                iteration_context_template: '',
                assembly_template: defaultAssemblyTemplates?.continuation_prompt || "{base_prompt}{iteration_context_template}"
            },
            report_prompt: {
                report_instructions: '',
                assembly_template: defaultAssemblyTemplates?.report_prompt || "{report_instructions}"
            },
            variable_registry: {}
        };

        fetch('/api/prompts/presets', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                preset_name: presetName,
                preset_data: presetData
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                WebUIUtils.showSuccess(`Preset "${presetName}" created successfully`);
                loadPresetList();
                // Select the new preset
                setTimeout(() => {
                    document.getElementById('preset-select').value = presetName;
                    loadPreset(presetName);
                }, 500);
            } else {
                WebUIUtils.showError(data.error || 'Failed to create preset');
            }
        })
        .catch(error => {
            console.error('Error creating preset:', error);
            WebUIUtils.showError('Failed to create preset');
        });
    }

    function loadVariableRegistry() {
        fetch('/api/prompts/variables')
            .then(response => response.json())
            .then(data => {
                variableRegistry = data.variable_registry || {};
                displayVariableRegistry(variableRegistry);
            })
            .catch(error => {
                console.error('Error loading variable registry:', error);
            });
    }

    function loadDefaultAssemblyTemplates() {
        // Try to fetch assembly templates from default preset
        fetch('/api/prompts/presets/default')
            .then(response => response.json())
            .then(data => {
                defaultAssemblyTemplates = {
                    base_prompt: data.base_prompt?.assembly_template || "Database schema:\n{schema}\n\n{tools_description}\n\n{domain_context}\n\n{task_instructions}",
                    verification_prompt: data.verification_prompt?.assembly_template || "{base_prompt}\n\n{memory_summary}\n\n{verification_task_template}",
                    continuation_prompt: data.continuation_prompt?.assembly_template || "{base_prompt}{iteration_context_template}",
                    report_prompt: data.report_prompt?.assembly_template || "{report_instructions}"
                };
            })
            .catch(error => {
                console.error('Error loading default assembly templates, using fallback:', error);
                // Fallback to hardcoded if default preset not available
                defaultAssemblyTemplates = {
                    base_prompt: "Database schema:\n{schema}\n\n{tools_description}\n\n{domain_context}\n\n{task_instructions}",
                    verification_prompt: "{base_prompt}\n\n{memory_summary}\n\n{verification_task_template}",
                    continuation_prompt: "{base_prompt}{iteration_context_template}",
                    report_prompt: "{report_instructions}"
                };
            });
    }

    function displayVariableRegistry(registry) {
        const variablesList = document.getElementById('variables-list');
        variablesList.innerHTML = '';

        Object.entries(registry).forEach(([varName, varInfo]) => {
            const varItem = document.createElement('div');
            varItem.className = 'variable-item';

            const varNameEl = document.createElement('div');
            varNameEl.className = 'variable-name';
            varNameEl.textContent = `{{${varName}}}`;

            const varDesc = document.createElement('div');
            varDesc.className = 'variable-description';
            varDesc.textContent = varInfo.description;

            const varDetails = document.createElement('div');
            varDetails.className = 'variable-details';

            const typeDetail = document.createElement('span');
            typeDetail.className = 'variable-detail';
            typeDetail.innerHTML = `<strong>Type:</strong> ${varInfo.type}`;

            const sourceDetail = document.createElement('span');
            sourceDetail.className = 'variable-detail';
            sourceDetail.innerHTML = `<strong>Source:</strong> ${varInfo.source}`;

            const scopeDetail = document.createElement('span');
            scopeDetail.className = 'variable-detail';
            scopeDetail.innerHTML = `<strong>Scope:</strong> ${Array.isArray(varInfo.scope) ? varInfo.scope.join(', ') : varInfo.scope}`;

            varDetails.appendChild(typeDetail);
            varDetails.appendChild(sourceDetail);
            varDetails.appendChild(scopeDetail);

            varItem.appendChild(varNameEl);
            varItem.appendChild(varDesc);
            varItem.appendChild(varDetails);

            variablesList.appendChild(varItem);
        });
    }

    function highlightPlaceholders() {
        // This could be enhanced with syntax highlighting
        // For now, it's a placeholder for future enhancement
        const codeEditors = document.querySelectorAll('.code-editor');
        codeEditors.forEach(editor => {
            // Future: Add syntax highlighting for {{VARIABLE}} placeholders
        });
    }

})();
