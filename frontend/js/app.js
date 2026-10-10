// =====================================================================
// Everest Textile Manufacturing System (ETMS) - Main UI Controller
// =====================================================================

document.addEventListener("DOMContentLoaded", async () => {
    // 1. Initialize State & Audio
    let autoSimTimer = null;
    let isAutoSimRunning = false;

    // Check backend health
    await store.checkBackendHealth();
    updateHUDStatus();

    // 2. Scene Navigation Tabs
    const navTabs = document.querySelectorAll(".nav-tab");
    const sceneViews = document.querySelectorAll(".scene-view");

    navTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            soundManager.playClick();
            navTabs.forEach(t => t.classList.remove("active"));
            sceneViews.forEach(v => v.classList.remove("active"));

            tab.classList.add("active");
            const targetSceneId = tab.dataset.scene;
            const targetScene = document.getElementById(targetSceneId);
            if (targetScene) {
                targetScene.classList.add("active");
                renderActiveScene(targetSceneId);
            }
        });
    });

    // 3. Audio Toggle
    const soundToggleBtn = document.getElementById("soundToggleBtn");
    soundToggleBtn.addEventListener("click", () => {
        soundManager.isMuted = !soundManager.isMuted;
        soundToggleBtn.textContent = soundManager.isMuted ? "🔇 AUDIO: MUTED" : "🔊 AUDIO: ON";
        if (!soundManager.isMuted) soundManager.playSuccessChime();
    });

    // 3b. LoomTrack Enterprise Role Authentication Modal
    const rolePortalBtn = document.getElementById("rolePortalBtn");
    const roleAuthModal = document.getElementById("roleAuthModal");
    const closeRoleModalBtn = document.getElementById("closeRoleModalBtn");
    const roleTabs = document.querySelectorAll("#roleTabs button");
    const roleBadgeText = document.getElementById("roleBadgeText");
    const roleGreeting = document.getElementById("roleGreeting");
    const roleUsernameInput = document.getElementById("roleUsernameInput");
    const rolePasswordInput = document.getElementById("rolePasswordInput");
    const roleCredentialsDemo = document.getElementById("roleCredentialsDemo");
    const roleAuthForm = document.getElementById("roleAuthForm");

    const roleConfigs = {
        owner: {
            badge: "OWNER ACCESS",
            badgeClass: "status-idle",
            greeting: "Good morning, Arun.",
            user: "owner",
            pass: "owner123",
            targetScene: "scene-floor"
        },
        admin: {
            badge: "ADMINISTRATOR",
            badgeClass: "status-running",
            greeting: "Welcome, Mill Operations Admin.",
            user: "admin",
            pass: "admin123",
            targetScene: "scene-gate"
        },
        employee: {
            badge: "FLOOR OPERATOR",
            badgeClass: "status-running",
            greeting: "Shift B Active: Operator Terminal.",
            user: "worker",
            pass: "worker123",
            targetScene: "scene-qc"
        },
        customer: {
            badge: "BUYER PORTAL",
            badgeClass: "status-maint",
            greeting: "Zara / Marks & Spencer Portal.",
            user: "buyer",
            pass: "buyer123",
            targetScene: "scene-customer"
        }
    };

    let selectedRole = "owner";

    if (rolePortalBtn && roleAuthModal) {
        rolePortalBtn.addEventListener("click", () => {
            soundManager.playClick();
            roleAuthModal.style.display = "flex";
        });

        closeRoleModalBtn.addEventListener("click", () => {
            soundManager.playClick();
            roleAuthModal.style.display = "none";
        });

        roleTabs.forEach(tab => {
            tab.addEventListener("click", () => {
                soundManager.playClick();
                roleTabs.forEach(t => {
                    t.style.borderBottom = "none";
                    t.classList.remove("active");
                });
                tab.classList.add("active");
                tab.style.borderBottom = "2px solid var(--status-idle)";
                
                selectedRole = tab.dataset.role;
                const cfg = roleConfigs[selectedRole];
                roleBadgeText.textContent = cfg.badge;
                roleGreeting.textContent = cfg.greeting;
                roleUsernameInput.value = cfg.user;
                rolePasswordInput.value = cfg.pass;
                roleCredentialsDemo.textContent = `${cfg.user} / ${cfg.pass}`;
            });
        });

        roleAuthForm.addEventListener("submit", (e) => {
            e.preventDefault();
            soundManager.playSuccessChime();
            roleAuthModal.style.display = "none";
            rolePortalBtn.textContent = `👤 ${selectedRole.toUpperCase()}`;

            // Navigate to the role's primary operational scene
            const cfg = roleConfigs[selectedRole];
            const targetTab = document.querySelector(`.nav-tab[data-scene='${cfg.targetScene}']`);
            if (targetTab) targetTab.click();
        });
    }

    // 3c. Industrial Item Passport Controller & Dual-Unit Calculator
    const itemPassportModal = document.getElementById("itemPassportModal");
    const closePassportBtn = document.getElementById("closePassportBtn");
    const passportTabs = document.querySelectorAll("#passportTabs .passport-tab");
    const passportPanes = document.querySelectorAll(".passport-tab-pane");

    if (closePassportBtn && itemPassportModal) {
        closePassportBtn.addEventListener("click", () => {
            soundManager.playClick();
            itemPassportModal.style.display = "none";
        });

        passportTabs.forEach(tab => {
            tab.addEventListener("click", () => {
                soundManager.playClick();
                passportTabs.forEach(t => t.classList.remove("active"));
                passportPanes.forEach(p => p.style.display = "none");

                tab.classList.add("active");
                const targetPane = document.getElementById(tab.dataset.tab);
                if (targetPane) targetPane.style.display = "block";
            });
        });

        // Dual-Unit Inline Calculator (Meters <-> Kg via GSM formula)
        const calcMetersInput = document.getElementById("calcMetersInput");
        const calcKgOutput = document.getElementById("calcKgOutput");
        if (calcMetersInput && calcKgOutput) {
            calcMetersInput.addEventListener("input", (e) => {
                const meters = parseFloat(e.target.value) || 0;
                // Formula: Weight (kg) = Length (m) * (Width 1.48m * GSM 125) / 1000
                const kg = (meters * 1.48 * 125) / 1000;
                calcKgOutput.textContent = `${kg.toFixed(2)} KG`;
            });
        }
    }

    window.openItemPassport = (orderId) => {
        soundManager.playClick();
        const order = store.state.orders.find(o => o.order_id === orderId) || store.state.orders[0];
        if (order) {
            document.getElementById("passportTitle").textContent = `${order.order_number}: ${order.fabric_specification}`;
            document.getElementById("passComp").textContent = order.fabric_specification.includes("Cotton") ? "100% Combed Cotton" : (order.fabric_specification.includes("Rayon") ? "100% Viscose Rayon" : "100% Poly Filament");
        }
        itemPassportModal.style.display = "flex";
    };

    // 3d. Invisible Hardware Barcode / RFID Keyboard Listener
    // Workers with handheld lasers stream keystrokes ending in Enter
    let barcodeBuffer = "";
    let lastKeyTime = Date.now();

    window.addEventListener("keydown", (e) => {
        // If user is typing in an active input field, let normal typing occur
        if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) {
            return;
        }

        const now = Date.now();
        if (now - lastKeyTime > 350) {
            barcodeBuffer = ""; // Reset buffer if slow human typing
        }
        lastKeyTime = now;

        if (e.key === "Enter") {
            if (barcodeBuffer.trim().length >= 4) {
                const scannedBarcode = barcodeBuffer.trim().toUpperCase();
                console.log(`[ETMS HARDWARE SCANNER TRIGGERED]: ${scannedBarcode}`);
                barcodeBuffer = "";
                
                // Route to Roll inspection or Dispatch automatically
                const matchingRoll = store.state.rolls.find(r => r.roll_barcode.toUpperCase() === scannedBarcode);
                if (matchingRoll) {
                    soundManager.playSuccessChime();
                    const qcTab = document.querySelector(".nav-tab[data-scene='scene-qc']");
                    if (qcTab) qcTab.click();
                    setTimeout(() => {
                        window.setQcBarcode(matchingRoll.roll_barcode);
                    }, 100);
                } else {
                    // Check if yarn lot
                    const matchingLot = store.state.batches.find(b => b.lot_number.toUpperCase() === scannedBarcode);
                    if (matchingLot) {
                        soundManager.playSuccessChime();
                        const gateTab = document.querySelector(".nav-tab[data-scene='scene-gate']");
                        if (gateTab) gateTab.click();
                    } else {
                        soundManager.playAlarmBuzzer();
                    }
                }
            }
        } else if (e.key.length === 1) {
            barcodeBuffer += e.key;
        }
    });

    // 3e. Factory Master Simulation Bar & Live Time Engine
    const simClockTime = document.getElementById("simClockTime");
    const simShiftBadge = document.getElementById("simShiftBadge");
    const toggleSimPlayBtn = document.getElementById("toggleSimPlayBtn");
    const injectWeftBreakBtn = document.getElementById("injectWeftBreakBtn");
    const simSpeedDials = document.querySelectorAll("#simSpeedDials button");

    if (simSpeedDials) {
        simSpeedDials.forEach(btn => {
            btn.addEventListener("click", () => {
                soundManager.playClick();
                simSpeedDials.forEach(b => {
                    b.classList.remove("active");
                    b.style.background = "transparent";
                    b.style.color = "#0f172a";
                });
                btn.classList.add("active");
                btn.style.background = "#0f172a";
                btn.style.color = "#ffffff";
                const speed = parseInt(btn.dataset.speed, 10) || 1;
                store.setSimulationSpeed(speed);
            });
        });
    }

    if (toggleSimPlayBtn) {
        toggleSimPlayBtn.addEventListener("click", () => {
            soundManager.playClick();
            store.toggleSimulationPlayback();
            if (store.isSimulationRunning) {
                toggleSimPlayBtn.textContent = "⏸ Pause";
                toggleSimPlayBtn.classList.remove("btn-primary");
                toggleSimPlayBtn.classList.add("btn-ghost");
            } else {
                toggleSimPlayBtn.textContent = "▶ Resume";
                toggleSimPlayBtn.classList.add("btn-primary");
                toggleSimPlayBtn.classList.remove("btn-ghost");
            }
        });
    }

    if (injectWeftBreakBtn) {
        injectWeftBreakBtn.addEventListener("click", () => {
            soundManager.playAlarmBuzzer();
            store.triggerMachineFault("WEAVE-LOOM-01", "WEFT_BREAK");
            // Also notify user with alert animation
            injectWeftBreakBtn.textContent = "💥 FAULT INJECTED (LOOM 01)";
            injectWeftBreakBtn.style.background = "#ffe4e6";
            setTimeout(() => {
                injectWeftBreakBtn.textContent = "⚠️ Inject Weft Break (Loom 01)";
                injectWeftBreakBtn.style.background = "transparent";
            }, 3000);
        });
    }

    // 3f. Real-Time Machine Tuning Modal Controller
    const machineTuningModal = document.getElementById("machineTuningModal");
    const closeTuneModalBtn = document.getElementById("closeTuneModalBtn");
    const cancelTuneBtn = document.getElementById("cancelTuneBtn");
    const machineTuningForm = document.getElementById("machineTuningForm");

    window.openMachineTuning = (machineId) => {
        soundManager.playClick();
        const m = store.state.machines.find(x => x.machine_id === machineId);
        if (!m || !machineTuningModal) return;

        document.getElementById("tuneMachineId").value = m.machine_id;
        document.getElementById("tuneMachineTitle").textContent = `${m.machine_id} Live Tuning`;
        document.getElementById("tuneStatusSelect").value = m.current_status;
        document.getElementById("tuneRpmInput").value = m.current_rpm || (m.rated_capacity_rpm > 1000 ? 11800 : 740);
        document.getElementById("tuneTensionInput").value = m.warp_tension_cn || 180;
        document.getElementById("tuneAmpsInput").value = m.current_power_draw_amps || 15.4;
        document.getElementById("tuneOrderIdInput").value = m.assigned_order_id || "ord-zara-081";
        document.getElementById("tuneOverheadInput").value = m.overhead_hourly_rate || 18.50;

        machineTuningModal.style.display = "flex";
    };

    if (closeTuneModalBtn && machineTuningModal) {
        closeTuneModalBtn.addEventListener("click", () => {
            machineTuningModal.style.display = "none";
        });
        cancelTuneBtn.addEventListener("click", () => {
            machineTuningModal.style.display = "none";
        });

        machineTuningForm.addEventListener("submit", (e) => {
            e.preventDefault();
            soundManager.playSuccessChime();
            const machineId = document.getElementById("tuneMachineId").value;
            const newStatus = document.getElementById("tuneStatusSelect").value;
            const newRpm = parseInt(document.getElementById("tuneRpmInput").value, 10) || 0;
            const newTension = parseInt(document.getElementById("tuneTensionInput").value, 10) || 180;
            const newAmps = parseFloat(document.getElementById("tuneAmpsInput").value) || 15.4;
            const newOrder = document.getElementById("tuneOrderIdInput").value.trim() || null;
            const newOverhead = parseFloat(document.getElementById("tuneOverheadInput").value) || 18.50;

            store.updateMachineConfiguration(machineId, {
                current_status: newStatus,
                current_rpm: newRpm,
                warp_tension_cn: newTension,
                current_power_draw_amps: newAmps,
                assigned_order_id: newOrder,
                overhead_hourly_rate: newOverhead,
                idle_seconds: newStatus === "RUNNING" ? 0 : 30,
                is_idle_alert: newStatus !== "RUNNING"
            });

            machineTuningModal.style.display = "none";
            store.notify();
        });
    }

    // 4. Initial Render of All Modules
    renderFloorHUD();
    renderGateInward();
    renderQCBench();
    renderDispatchTerminal();
    renderCustomerPortal("ORD-2026-081");
    renderFinancialRollup("ord-zara-081");

    // Subscribe to state changes
    store.subscribe(() => {
        updateHUDStatus();
        updateSimulationClock();
        const activeTab = document.querySelector(".nav-tab.active");
        if (activeTab) {
            renderActiveScene(activeTab.dataset.scene);
        }
    });

    function updateSimulationClock() {
        if (!simClockTime || !simShiftBadge) return;
        const clockData = store.getSimulationTimeFormatted();
        simClockTime.textContent = clockData.timeStr;
        simShiftBadge.textContent = clockData.shiftName;
    }


    function renderActiveScene(sceneId) {
        if (sceneId === "scene-floor") renderFloorHUD();
        else if (sceneId === "scene-gate") renderGateInward();
        else if (sceneId === "scene-qc") renderQCBench();
        else if (sceneId === "scene-dispatch") renderDispatchTerminal();
        else if (sceneId === "scene-customer") {
            const ord = document.getElementById("custOrderSearchInput").value || "ORD-2026-081";
            renderCustomerPortal(ord);
        } else if (sceneId === "scene-financial") {
            const ordId = document.getElementById("costingOrderSelect").value || "ord-zara-081";
            renderFinancialRollup(ordId);
        }
    }

    function updateHUDStatus() {
        const pulse = document.getElementById("backendPulse");
        const statusText = document.getElementById("edgeStatusText");
        if (store.isBackendOnline) {
            pulse.classList.remove("offline");
            statusText.textContent = "ONLINE (FASTAPI)";
        } else {
            pulse.classList.add("offline");
            statusText.textContent = "CLIENT DB (RESILIENT)";
        }

        const runningLooms = store.state.machines.filter(m => m.current_status === "RUNNING").length;
        document.getElementById("activeLoomsCount").textContent = `${runningLooms} / ${store.state.machines.length}`;

        // Global PPS (~ running looms * 12 picks/sec)
        document.getElementById("globalPickRate").textContent = `${runningLooms * 12} PPS`;
    }

    // =================================================================
    // SCENE 1: PRODUCTION FLOOR HUD
    // =================================================================
    function renderFloorHUD() {
        const spinningCont = document.getElementById("spinningMachinesContainer");
        const weavingCont = document.getElementById("weavingMachinesContainer");
        const dyeingCont = document.getElementById("dyeingMachinesContainer");

        spinningCont.innerHTML = "";
        weavingCont.innerHTML = "";
        dyeingCont.innerHTML = "";

        let totalPicks = 0;
        let totalAmps = 0.0;
        let idleAlerts = 0;

        store.state.machines.forEach(m => {
            totalPicks += m.current_picks_cumulative;
            totalAmps += m.current_power_draw_amps;
            if (m.is_idle_alert) idleAlerts++;

            const card = createMachineCard(m);
            if (m.stage === "SPINNING") spinningCont.appendChild(card);
            else if (m.stage === "WEAVING") weavingCont.appendChild(card);
            else if (m.stage === "DYEING") dyeingCont.appendChild(card);
        });

        document.getElementById("totalPicksDisplay").textContent = totalPicks.toLocaleString();
        document.getElementById("totalPowerAmps").textContent = `${totalAmps.toFixed(1)} A`;
        document.getElementById("idleAlertsCount").textContent = `${idleAlerts} Machine${idleAlerts === 1 ? '' : 's'}`;

        // Draw real-time sparkline waveforms for each machine
        store.state.machines.forEach(m => {
            drawMachineSparkline(m.machine_id, m.current_status);
        });
    }

    function drawMachineSparkline(machineId, status) {
        const canvas = document.getElementById(`sparkline_${machineId}`);
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const history = store.telemetryHistory[machineId] || [];
        if (history.length < 2) return;

        // Base line
        ctx.beginPath();
        ctx.strokeStyle = status === "RUNNING" ? "#0284c7" : "#cbd5e1";
        ctx.lineWidth = 1.75;
        ctx.lineJoin = "round";

        const points = history.map(pt => pt.rpm);
        const minVal = Math.min(...points) * 0.95;
        const maxVal = Math.max(...points) * 1.05 || 1;
        const range = (maxVal - minVal) || 1;

        const stepX = w / (points.length - 1);
        points.forEach((val, i) => {
            const x = i * stepX;
            const normY = status === "RUNNING" ? (val - minVal) / range : 0.5;
            const y = h - (normY * (h - 6) + 3);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();

        // Pulsing tip at end of waveform
        if (status === "RUNNING") {
            const lastVal = points[points.length - 1];
            const normY = (lastVal - minVal) / range;
            const lastY = h - (normY * (h - 6) + 3);
            ctx.fillStyle = "#0284c7";
            ctx.beginPath();
            ctx.arc(w - 2, lastY, 2.5, 0, Math.PI * 2);
            ctx.fill();
        }
    }


    function createMachineCard(m) {
        const div = document.createElement("div");
        const isIdleAlert = m.is_idle_alert;
        const statusClass = m.current_status.toLowerCase();

        div.className = `machine-card ${statusClass} ${isIdleAlert ? 'idle-alert' : ''}`;

        // Stage-Specific Industrial Textile Telemetry
        let specRows = "";
        if (m.stage === "WEAVING") {
            specRows = `
                <div class="textile-subgrid">
                    <div class="t-cell"><span class="t-lbl">TYPE</span><span class="t-val">${m.loom_type || 'Airjet'}</span></div>
                    <div class="t-cell"><span class="t-lbl">REED</span><span class="t-val">${m.reed_width_cm || 190} cm</span></div>
                    <div class="t-cell"><span class="t-lbl">WARP YARN</span><span class="t-val mono">${m.warp_count || '60s Ne'}</span></div>
                    <div class="t-cell"><span class="t-lbl">WEFT YARN</span><span class="t-val mono">${m.weft_count || '60s Ne'}</span></div>
                    <div class="t-cell"><span class="t-lbl">PICKS/CM</span><span class="t-val mono">${m.picks_per_cm || 28.5}</span></div>
                    <div class="t-cell"><span class="t-lbl">WARP TENS</span><span class="t-val mono">${m.warp_tension_cn || 180} cN</span></div>
                    <div class="t-cell"><span class="t-lbl">INSERTION</span><span class="t-val mono">${m.weft_insertion_m_min || 0} m/min</span></div>
                    <div class="t-cell"><span class="t-lbl">STOPS (W/F)</span><span class="t-val mono">${m.warp_stops_shift ?? 0} / ${m.weft_stops_shift ?? 0}</span></div>
                </div>
            `;
        } else if (m.stage === "SPINNING") {
            specRows = `
                <div class="textile-subgrid">
                    <div class="t-cell"><span class="t-lbl">SPINDLES</span><span class="t-val mono">${m.spindles_active || '1,008'}</span></div>
                    <div class="t-cell"><span class="t-lbl">YARN COUNT</span><span class="t-val mono">${m.yarn_count_spec || '60s Ne'}</span></div>
                    <div class="t-cell"><span class="t-lbl">TWIST MULT</span><span class="t-val mono">${m.twist_multiplier || '3.85 TM'}</span></div>
                    <div class="t-cell"><span class="t-lbl">BREAK RATE</span><span class="t-val mono">${m.end_breakage_rate || '1.2/k'}</span></div>
                    <div class="t-cell"><span class="t-lbl">EFFICIENCY</span><span class="t-val mono">${m.running_efficiency_pct || 0}%</span></div>
                    <div class="t-cell"><span class="t-lbl">DOFF TIMER</span><span class="t-val mono">${m.doff_timer_min || 0} min</span></div>
                </div>
            `;
        } else if (m.stage === "DYEING") {
            specRows = `
                <div class="textile-subgrid">
                    <div class="t-cell"><span class="t-lbl">MACHINE</span><span class="t-val">${m.dye_machine_type || 'Soft Flow'}</span></div>
                    <div class="t-cell"><span class="t-lbl">LIQUOR RATIO</span><span class="t-val mono">${m.liquor_ratio || '1:6'}</span></div>
                    <div class="t-cell"><span class="t-lbl">TEMP C</span><span class="t-val mono ${m.vat_temp_celsius > 90 ? 'amber' : ''}">${m.vat_temp_celsius || 24}°C</span></div>
                    <div class="t-cell"><span class="t-lbl">pH LEVEL</span><span class="t-val mono">${m.ph_level || 6.5}</span></div>
                    <div class="t-cell"><span class="t-lbl">ΔE TOLERANCE</span><span class="t-val mono">${m.delta_e_tolerance || 0.4}</span></div>
                    <div class="t-cell"><span class="t-lbl">RECIPE</span><span class="t-val mono">${m.recipe_id || 'NONE'}</span></div>
                </div>
            `;
        }

        div.innerHTML = `
            <div class="machine-header">
                <div>
                    <span class="machine-id">${m.machine_id}</span>
                    <div style="font-size: 0.72rem; color: #64748b; font-family: var(--font-mono);">${m.stage} · ${m.assigned_order_id ? m.assigned_order_id.toUpperCase() : 'NO ORDER'}</div>
                </div>
                <span class="status-badge ${m.current_status}">${m.current_status}</span>
            </div>
            
            <div class="telemetry-metrics-grid">
                <div class="metric-item">
                    <span class="metric-label">Loom Speed (RPM)</span>
                    <span class="metric-val ${m.current_status === 'RUNNING' ? 'green' : 'amber'}">${m.current_rpm || 0} RPM</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Motor Load</span>
                    <span class="metric-val ${m.current_status === 'RUNNING' ? 'cyan' : ''}">${m.current_power_draw_amps.toFixed(1)} A</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Picks Cumulative</span>
                    <span class="metric-val">${m.current_picks_cumulative.toLocaleString()}</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Idle Inactivity</span>
                    <span class="metric-val ${m.idle_seconds > 120 ? 'amber' : ''}">${m.idle_seconds}s</span>
                </div>
            </div>

            <!-- Live 30-Second Rolling Waveform Sparkline -->
            <div style="margin: 0.5rem 0 0.25rem 0; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px 8px; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.65rem; font-family: var(--font-mono); color: #64748b; font-weight: 600;">LIVE OSCILLATION (RPM / cN)</span>
                <canvas id="sparkline_${m.machine_id}" width="140" height="24" style="display: block;"></canvas>
            </div>

            ${specRows}

            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px solid #f1f5f9;">
                <span style="font-size: 0.72rem; color: #64748b; font-family: var(--font-mono);">Overhead: $${m.overhead_hourly_rate.toFixed(2)}/hr</span>
                <div style="display: flex; gap: 6px;">
                    <button class="btn btn-ghost" style="padding: 0.25rem 0.55rem; font-size: 0.7rem; border-radius: 4px; border-color: #cbd5e1;" onclick="openMachineTuning('${m.machine_id}')" title="Dynamically tune RPM, load, and tension">
                        ⚙️ Tune
                    </button>
                    <button class="btn btn-ghost" style="padding: 0.25rem 0.55rem; font-size: 0.7rem; border-radius: 4px;" onclick="openItemPassport('${m.assigned_order_id || 'ord-zara-081'}')">
                        📋 Specs
                    </button>
                    <button class="btn btn-ghost" style="padding: 0.25rem 0.55rem; font-size: 0.7rem; border-radius: 4px;" onclick="toggleMachine('${m.machine_id}')">
                        ${m.current_status === 'RUNNING' ? 'Pause' : 'Start'}
                    </button>
                </div>
            </div>

        `;
        return div;
    }

    window.toggleMachine = (id) => {
        soundManager.playClick();
        store.toggleMachineState(id);
    };

    // Edge Simulator Controls
    document.getElementById("triggerPulseBtn").addEventListener("click", () => {
        soundManager.playClick();
        store.tickTelemetry();
    });

    document.getElementById("toggleBenchmarkLoomBtn").addEventListener("click", () => {
        soundManager.playClick();
        store.toggleMachineState("WEAVE-LOOM-04");
    });

    const autoSimBtn = document.getElementById("autoSimulateBtn");
    autoSimBtn.addEventListener("click", () => {
        soundManager.playClick();
        isAutoSimRunning = !isAutoSimRunning;
        if (isAutoSimRunning) {
            autoSimBtn.textContent = "⏸ Stop Auto-Loop";
            autoSimBtn.classList.add("btn-danger");
            autoSimBtn.classList.remove("btn-primary");
            autoSimTimer = setInterval(() => store.tickTelemetry(), 1000);
        } else {
            autoSimBtn.textContent = "▶ Start Auto-Loop (1s Interval)";
            autoSimBtn.classList.remove("btn-danger");
            autoSimBtn.classList.add("btn-primary");
            clearInterval(autoSimTimer);
        }
    });

    // =================================================================
    // SCENE 2: GATE INWARD & SAFETY STOCK
    // =================================================================
    function renderGateInward() {
        const list = document.getElementById("yarnInventoryList");
        list.innerHTML = "";

        let hasLowStock = false;
        let lowStockLot = null;

        store.state.batches.forEach(b => {
            const isLow = b.current_stock_kg < b.safety_stock_threshold_kg;
            if (isLow) {
                hasLowStock = true;
                lowStockLot = b;
            }

            const item = document.createElement("div");
            item.className = `yarn-stock-card ${isLow ? 'critical' : ''}`;
            item.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span class="color-swatch" style="background-color: ${b.color_code}"></span>
                        <strong style="font-family: var(--font-mono); font-size: 0.95rem; color: #fff;">${b.lot_number}</strong>
                    </div>
                    <span class="status-badge ${isLow ? 'IDLE' : 'RUNNING'}">
                        ${isLow ? '⚠️ REORDER NEEDED' : 'IN STOCK'}
                    </span>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin: 0.4rem 0;">
                    ${b.material_type.replace('_', ' ')} | Supplier: <strong style="color: #fff;">${b.supplier_name}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.8rem; font-family: var(--font-mono);">
                    <span>Stock: <strong style="color: ${isLow ? '#fbbf24' : '#34d399'};">${b.current_stock_kg} kg</strong></span>
                    <span>Safety Min: ${b.safety_stock_threshold_kg} kg</span>
                    <span>Cost: $${b.cost_per_kg}/kg</span>
                </div>
            `;
            list.appendChild(item);
        });

        const warningBanner = document.getElementById("safetyStockWarningBanner");
        const badge = document.getElementById("stockAlertBadge");
        if (hasLowStock) {
            warningBanner.style.display = "flex";
            badge.style.display = "inline-block";
            document.getElementById("safetyStockWarningDetails").textContent = 
                `Lot ${lowStockLot.lot_number} current stock is ${lowStockLot.current_stock_kg} kg, which is below the ${lowStockLot.safety_stock_threshold_kg} kg threshold! Immediate reorder notification issued.`;
        } else {
            warningBanner.style.display = "none";
            badge.style.display = "none";
        }
    }

    // Scale Weighed Simulation
    document.getElementById("simulateScaleWeighBtn").addEventListener("click", () => {
        soundManager.playClick();
        const randomWeights = [480.5, 520.0, 415.0, 600.0, 390.5];
        const chosen = randomWeights[Math.floor(Math.random() * randomWeights.length)];
        document.getElementById("scaleWeightVal").textContent = chosen.toFixed(2);
        document.getElementById("weightKgInput").value = chosen.toFixed(1);
    });

    // Inward Form Submission
    document.getElementById("inwardYarnForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        soundManager.playClick();

        const lotNum = document.getElementById("lotNumberInput").value.trim();
        const supplier = document.getElementById("supplierNameInput").value.trim();
        const matType = document.getElementById("materialTypeSelect").value;
        const color = document.getElementById("colorCodeInput").value;
        const weight = parseFloat(document.getElementById("weightKgInput").value);
        const cost = parseFloat(document.getElementById("costPerKgInput").value);
        const safety = parseFloat(document.getElementById("safetyThresholdInput").value);

        try {
            const res = await store.addInwardYarn({
                lot_number: lotNum,
                supplier_name: supplier,
                material_type: matType,
                color_code: color,
                weight_kg: weight,
                cost_per_kg: cost,
                safety_stock_threshold_kg: safety
            });

            soundManager.playSuccessChime();
            alert(`✅ Pallet ${lotNum} (${weight} kg) booked into inward ledger!`);
            document.getElementById("lotNumberInput").value = "";
            renderGateInward();
        } catch (err) {
            soundManager.playAlarmBuzzer();
            alert(`❌ Inward Booking Error: ${err.message}`);
        }
    });

    // =================================================================
    // SCENE 3: QUALITY CONTROL & ASTM D5430 BENCH (REFINED STUDIO EDITION)
    // =================================================================
    let currentQcFilter = "ALL";

    // Filter Chips Event Binding
    const qcFilterBtns = document.querySelectorAll("#qcFilterTabs .filter-chip");
    qcFilterBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            soundManager.playClick();
            qcFilterBtns.forEach(b => {
                b.classList.remove("active");
                b.style.background = "transparent";
                b.style.color = "var(--text-muted)";
            });
            btn.classList.add("active");
            btn.style.background = "#fff";
            btn.style.color = "#000";
            currentQcFilter = btn.dataset.filter;
            renderQCBench();
        });
    });

    function renderQCBench() {
        const rolls = store.state.rolls;

        // Metric Card Updates
        const pendingRolls = rolls.filter(r => r.qc_status === "PENDING");
        const reworkRolls = rolls.filter(r => r.qc_status === "REWORK");
        const passedRolls = rolls.filter(r => r.qc_status === "PASSED");
        const passRate = rolls.length > 0 ? ((passedRolls.length / rolls.length) * 100).toFixed(1) : "94.2";

        const pendingCountEl = document.getElementById("qcPendingCount");
        if (pendingCountEl) pendingCountEl.textContent = pendingRolls.length;

        const passRateEl = document.getElementById("qcPassRate");
        if (passRateEl) passRateEl.textContent = `${passRate}%`;

        const reworkCountEl = document.getElementById("qcReworkCount");
        if (reworkCountEl) reworkCountEl.textContent = reworkRolls.length;

        const affectedRollsEl = document.getElementById("qcAffectedRolls");
        if (affectedRollsEl) affectedRollsEl.textContent = `${reworkRolls.length} roll${reworkRolls.length === 1 ? '' : 's'} affected`;

        // Render Porsche-Style Roll Table
        const listContainer = document.getElementById("porscheRollsList");
        if (listContainer) {
            listContainer.innerHTML = "";

            const filteredRolls = rolls.filter(r => {
                if (currentQcFilter === "ALL") return true;
                return r.qc_status === currentQcFilter;
            });

            if (filteredRolls.length === 0) {
                listContainer.innerHTML = `
                    <div style="padding: 2.5rem; text-align: center; color: #64748b; font-size: 0.9rem;">
                        No rolls matching the <strong>${currentQcFilter}</strong> inspection criteria.
                    </div>
                `;
            } else {
                filteredRolls.forEach(roll => {
                    const row = document.createElement("div");
                    row.className = "porsche-table-row";

                    // Operator Name lookup
                    const operatorMap = {
                        "OP-812": "Ravi Kumar",
                        "OP-403": "Meena Shah",
                        "OP-109": "Arjun Das",
                        "OP-301": "Suresh Patel"
                    };
                    const operatorName = operatorMap[roll.operator_id] || "Ravi Kumar";

                    // Defect Category Options
                    const defectOptions = [
                        { val: "NONE", label: "— Clean —" },
                        { val: "UNEVEN_WEAVING", label: "Uneven weaving" },
                        { val: "OIL_STAIN", label: "Oil stain" },
                        { val: "COLOR_MISMATCH", label: "Color mismatch" },
                        { val: "HOLE", label: "Cut / Hole" },
                        { val: "SLUB", label: "Yarn Slub" }
                    ];

                    let defectSelectHtml = `<select class="porsche-select-dropdown" onchange="updateRollDefect('${roll.roll_barcode}', this.value)">`;
                    defectOptions.forEach(opt => {
                        const isSel = (roll.defect_type || "NONE") === opt.val ? "selected" : "";
                        defectSelectHtml += `<option value="${opt.val}" ${isSel}>${opt.label}</option>`;
                    });
                    defectSelectHtml += `</select>`;

                    // Decision Button States
                    const isPass = roll.qc_status === "PASSED" ? "selected-pass" : "";
                    const isRework = roll.qc_status === "REWORK" ? "selected-rework" : "";
                    const isReject = roll.qc_status === "REJECTED" ? "selected-reject" : "";

                    row.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 14px;">
                            <div style="width: 44px; height: 44px; border-radius: 8px; background: #f1f5f9; display: grid; place-items: center; font-size: 1.25rem;">
                                🧵
                            </div>
                            <div>
                                <div class="porsche-roll-id">${roll.roll_barcode}</div>
                                <div class="porsche-roll-meta">${roll.length_meters}m · ${operatorName}</div>
                            </div>
                        </div>

                        <div>
                            <div style="font-weight: 700; font-size: 0.9rem; color: #0f172a;">${roll.order_id === 'ord-zara-081' ? 'ORD-1042' : 'ORD-1043'}</div>
                            <div style="font-size: 0.75rem; color: #64748b;">Machine ${roll.machine_id}</div>
                        </div>

                        <div>
                            ${defectSelectHtml}
                        </div>

                        <div>
                            <div class="porsche-decision-group">
                                <button class="porsche-btn-choice ${isPass}" onclick="quickVerdict('${roll.roll_barcode}', 'PASSED')">
                                    ✓ Pass
                                </button>
                                <button class="porsche-btn-choice ${isRework}" onclick="quickVerdict('${roll.roll_barcode}', 'REWORK')">
                                    Rework
                                </button>
                                <button class="porsche-btn-choice ${isReject}" onclick="quickVerdict('${roll.roll_barcode}', 'REJECTED')">
                                    ✕ Reject
                                </button>
                            </div>
                        </div>

                        <div style="text-align: right;">
                            <button class="porsche-arrow-btn" onclick="setQcBarcode('${roll.roll_barcode}')" title="Inspect Deep Lineage">
                                →
                            </button>
                        </div>
                    `;
                    listContainer.appendChild(row);
                });
            }
        }

        // Deep Inspection Preview Update
        const activeBarcode = document.getElementById("qcActiveBarcode") ? document.getElementById("qcActiveBarcode").textContent : "ROLL-081-PENDING-03";
        loadQCBarcodeData(activeBarcode);
    }

    window.updateRollDefect = (barcode, defectVal) => {
        soundManager.playClick();
        const roll = store.state.rolls.find(r => r.roll_barcode === barcode);
        if (roll) {
            roll.defect_type = defectVal;
            if (defectVal !== "NONE" && roll.defect_points === 0) {
                roll.defect_points = 5;
            }
            renderQCBench();
        }
    };

    window.quickVerdict = async (barcode, verdict) => {
        soundManager.playClick();
        const roll = store.state.rolls.find(r => r.roll_barcode === barcode);
        const defect = roll ? (roll.defect_type || "NONE") : "NONE";
        const points = roll ? (roll.defect_points || 0) : 0;

        try {
            await store.processQCInspection(barcode, verdict, defect, points, "OP-QC-LEAD");
            if (verdict === "PASSED") soundManager.playSuccessChime();
            else soundManager.playAlarmBuzzer();
            renderQCBench();
        } catch (e) {
            alert(`Decision error: ${e.message}`);
        }
    };

    function loadQCBarcodeData(barcode) {
        const roll = store.state.rolls.find(r => r.roll_barcode.toUpperCase() === barcode.toUpperCase()) || store.state.rolls[2];
        if (!roll) return;

        document.getElementById("qcActiveBarcode").textContent = roll.roll_barcode;
        document.getElementById("qcActiveCurrentStatus").textContent = roll.qc_status;
        document.getElementById("qcActiveCurrentStatus").className = `status-badge ${roll.qc_status === 'PASSED' ? 'RUNNING' : (roll.qc_status === 'REJECTED' ? 'IDLE' : '')}`;
        document.getElementById("qcActiveLength").textContent = `${roll.length_meters} m`;
        document.getElementById("qcActiveWeight").textContent = `${roll.gross_weight_kg} kg`;
        document.getElementById("qcActiveMachine").textContent = roll.machine_id;

        document.getElementById("qcDefectTypeSelect").value = roll.defect_type || "NONE";
        document.getElementById("qcDefectPointsInput").value = roll.defect_points || 0;

        // Render Linear Defect Coordinate Markers (ASTM D5430 Map)
        renderLinearRollDefects(roll);

        // Render Upstream Lineage
        const trace = store.getUpstreamLineage(roll.roll_barcode);
        if (trace) {
            document.getElementById("linOrderNum").textContent = trace.order ? trace.order.order_number : "ORD-2026-081";
            document.getElementById("linBuyerName").textContent = trace.order ? trace.order.buyer_name : "Zara Sourcing / Inditex";
            document.getElementById("linFabricSpec").textContent = trace.order ? trace.order.fabric_specification : "60s Combed Cotton Poplin";
            document.getElementById("linLoomId").textContent = trace.lineage.origin_machine_id;
            document.getElementById("linOperatorId").textContent = trace.lineage.operator_id;
            if (trace.lineage.yarn_batch) {
                document.getElementById("linYarnLot").textContent = trace.lineage.yarn_batch.lot_number;
            }
            document.getElementById("linRecommendedAction").textContent = trace.recommended_action;
        }
    }

    function renderLinearRollDefects(roll) {
        const markersContainer = document.getElementById("rollDefectMarkers");
        const coordLabel = document.getElementById("defectCoordinateLabel");
        if (!markersContainer) return;
        markersContainer.innerHTML = "";

        // If roll has no defects or points, show clean badge
        if (!roll.defect_type || roll.defect_type === "NONE") {
            if (coordLabel) coordLabel.textContent = "Clean Fabric Roll (0 Defects)";
            return;
        }

        // Plot realistic coordinate positions along roll length
        const rollLen = roll.length_meters || 135;
        // Default coordinate at ~ 42% or stored coordinate
        const coordMeters = roll.defect_meter_coordinate || (roll.defect_points > 10 ? 82.5 : 44.0);
        const pct = Math.min(98, Math.max(2, (coordMeters / rollLen) * 100));

        const marker = document.createElement("div");
        marker.style.position = "absolute";
        marker.style.left = `${pct}%`;
        marker.style.top = "2px";
        marker.style.bottom = "2px";
        marker.style.width = "8px";
        marker.style.transform = "translateX(-50%)";
        marker.style.background = roll.qc_status === "REJECTED" ? "#e11d48" : "#f59e0b";
        marker.style.borderRadius = "3px";
        marker.style.boxShadow = "0 0 6px rgba(225, 29, 72, 0.6)";
        marker.title = `Defect: ${roll.defect_type} at ${coordMeters.toFixed(1)}m (${roll.defect_points} pts)`;
        markersContainer.appendChild(marker);

        if (coordLabel) {
            coordLabel.textContent = `📍 ${roll.defect_type} detected at ${coordMeters.toFixed(1)}m / ${rollLen}m`;
        }
    }

    // Click handler for user to interactively plot a defect coordinate on the roll bar
    const linearRollBar = document.getElementById("linearRollBar");
    if (linearRollBar) {
        linearRollBar.addEventListener("click", (e) => {
            soundManager.playClick();
            const rect = linearRollBar.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const pct = Math.max(0, Math.min(1, clickX / rect.width));
            const activeBarcode = document.getElementById("qcActiveBarcode").textContent;
            const roll = store.state.rolls.find(r => r.roll_barcode.toUpperCase() === activeBarcode.toUpperCase());
            if (!roll) return;

            const rollLen = roll.length_meters || 135;
            const clickedMeters = Number((pct * rollLen).toFixed(1));
            roll.defect_meter_coordinate = clickedMeters;
            
            // If defect is NONE, auto-promote to UNEVEN_WEAVING
            if (!roll.defect_type || roll.defect_type === "NONE") {
                roll.defect_type = "UNEVEN_WEAVING";
                roll.defect_points = 4;
                document.getElementById("qcDefectTypeSelect").value = "UNEVEN_WEAVING";
                document.getElementById("qcDefectPointsInput").value = 4;
            }

            renderLinearRollDefects(roll);
            renderQCBench();
        });
    }

    window.setQcBarcode = (barcode) => {
        soundManager.playClick();
        document.getElementById("qcBarcodeScanInput").value = barcode;
        loadQCBarcodeData(barcode);
    };


    document.getElementById("loadRollForQcBtn").addEventListener("click", () => {
        soundManager.playClick();
        const barcode = document.getElementById("qcBarcodeScanInput").value.trim();
        loadQCBarcodeData(barcode);
    });

    // Verdict Handler
    async function applyQCVerdict(verdict) {
        soundManager.playClick();
        const barcode = document.getElementById("qcActiveBarcode").textContent;
        const defect = document.getElementById("qcDefectTypeSelect").value;
        const points = parseInt(document.getElementById("qcDefectPointsInput").value, 10);

        try {
            const res = await store.processQCInspection(barcode, verdict, defect, points, "OP-QC-INSPECTOR");
            if (verdict === "PASSED") {
                soundManager.playSuccessChime();
            } else {
                soundManager.playAlarmBuzzer();
            }

            const feedback = document.getElementById("qcResultFeedback");
            feedback.style.display = "block";
            feedback.style.background = verdict === "PASSED" ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)";
            feedback.style.color = verdict === "PASSED" ? "#34d399" : "#f87171";
            feedback.innerHTML = `<strong>${verdict} Verdict Applied:</strong> Roll ${barcode} evaluated as ${res.astm_grade} (${points} points). Lineage logged.`;

            loadQCBarcodeData(barcode);
        } catch (e) {
            alert(`QC Error: ${e.message}`);
        }
    }

    document.getElementById("btnVerdictPass").addEventListener("click", () => applyQCVerdict("PASSED"));
    document.getElementById("btnVerdictRework").addEventListener("click", () => applyQCVerdict("REWORK"));
    document.getElementById("btnVerdictReject").addEventListener("click", () => applyQCVerdict("REJECTED"));

    document.getElementById("holdLoomBtn").addEventListener("click", () => {
        soundManager.playAlarmBuzzer();
        const loomId = document.getElementById("linLoomId").textContent;
        alert(`🚨 LOOM CALIBRATION DISPATCHED: Loom ${loomId} placed on electrical & mechanical hold.`);
    });

    // =================================================================
    // SCENE 4: TRUCK DISPATCH TERMINAL (ANTI-DOUBLE DISPATCH)
    // =================================================================
    function renderDispatchTerminal() {
        const inv = document.getElementById("dispatchInvoiceInput").value.trim();
        const manifest = store.getManifest(inv);

        const tbody = document.getElementById("manifestTableBody");
        tbody.innerHTML = "";

        manifest.rolls.forEach(r => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong style="color: #fff; font-family: var(--font-mono);">${r.roll_barcode}</strong></td>
                <td>${r.length_meters} m</td>
                <td>${r.gross_weight_kg} kg</td>
                <td style="color: var(--text-dim); font-size: 0.75rem;">${new Date(r.dispatched_at).toLocaleTimeString()}</td>
                <td><span class="status-badge RUNNING">LOADED</span></td>
            `;
            tbody.appendChild(tr);
        });

        // Capacity Bar (Max 1500 kg per truck)
        const pct = Math.min(100, Math.round((manifest.total_weight_kg / 1500) * 100));
        document.getElementById("truckCapacityFill").style.width = `${pct}%`;
        document.getElementById("truckCapacityText").textContent = `${manifest.total_weight_kg.toFixed(1)} / 1,500 KG (${pct}%)`;
    }

    window.setDispatchTestBarcode = (barcode) => {
        soundManager.playClick();
        document.getElementById("dispatchBarcodeInput").value = barcode;
    };

    document.getElementById("dispatchScanForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        soundManager.playClick();

        const barcode = document.getElementById("dispatchBarcodeInput").value.trim();
        const invoice = document.getElementById("dispatchInvoiceInput").value.trim();
        const truck = document.getElementById("dispatchTruckInput").value.trim();

        try {
            const res = await store.dispatchRollToTruck(barcode, truck, invoice);
            soundManager.playSuccessChime();
            renderDispatchTerminal();
            document.getElementById("dispatchBarcodeInput").value = "";
        } catch (err) {
            soundManager.playAlarmBuzzer();
            if (err.message.includes("Double Dispatch Blocked")) {
                showDoubleDispatchModal(err.message);
            } else {
                alert(`❌ Dispatch Blocked: ${err.message}`);
            }
        }
    });

    function showDoubleDispatchModal(msg) {
        document.getElementById("alarmModalMessage").textContent = msg;
        document.getElementById("doubleDispatchAlarmModal").classList.add("active");
    }

    document.getElementById("closeAlarmModalBtn").addEventListener("click", () => {
        soundManager.playClick();
        document.getElementById("doubleDispatchAlarmModal").classList.remove("active");
    });

    // =================================================================
    // SCENE 5: CUSTOMER ORDER TRACKING (GAP 4 FIX!)
    // =================================================================
    async function renderCustomerPortal(orderNumber) {
        try {
            const data = await store.trackOrder(orderNumber);

            document.getElementById("custOrderTitle").textContent = `${data.order_number}: ${data.fabric_specification}`;
            document.getElementById("custBuyerName").textContent = data.buyer_name;
            document.getElementById("custDeadline").textContent = data.delivery_deadline;
            document.getElementById("custStatusBadge").textContent = data.order_status.replace('_', ' ');

            // Stepper Nodes
            const stepper = document.getElementById("custStepperNodes");
            stepper.innerHTML = "";

            data.milestones.forEach((m, idx) => {
                const node = document.createElement("div");
                node.className = `step-node ${m.status.toLowerCase()}`;
                node.innerHTML = `
                    <div class="step-circle">${m.status === 'COMPLETED' ? '✓' : idx + 1}</div>
                    <div class="step-label">${m.label}</div>
                    <div style="font-size: 0.65rem; color: var(--text-dim); margin-top: 0.2rem;">${m.timestamp || ''}</div>
                `;
                stepper.appendChild(node);
            });

            // Progress Meters
            document.getElementById("custProgressText").textContent = 
                `${data.passed_meters.toLocaleString()} / ${data.target_meters.toLocaleString()} METERS (${data.completion_percentage}%)`;
            document.getElementById("custProgressFill").style.width = `${data.completion_percentage}%`;

            // Quality Certificate
            document.getElementById("custGradeARate").textContent = `${data.quality_grade_a_rate}%`;

            // Notifications Feed
            const notifFeed = document.getElementById("custNotificationsFeed");
            notifFeed.innerHTML = "";
            if (data.notifications && data.notifications.length) {
                data.notifications.forEach(n => {
                    const row = document.createElement("div");
                    row.style.background = "rgba(0,0,0,0.25)";
                    row.style.padding = "0.6rem 0.8rem";
                    row.style.borderRadius = "8px";
                    row.style.borderLeft = "3px solid #38bdf8";
                    row.innerHTML = `
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-dim);">
                            <span>${n.channel} PUSH ALERT</span>
                            <span>${new Date(n.sent_at).toLocaleTimeString()}</span>
                        </div>
                        <div style="font-size: 0.85rem; color: #fff; margin-top: 0.2rem;">${n.message_body}</div>
                    `;
                    notifFeed.appendChild(row);
                });
            } else {
                notifFeed.innerHTML = `<div style="color: var(--text-dim); font-size: 0.85rem;">No customer alerts recorded yet.</div>`;
            }
        } catch (e) {
            alert(`Customer Portal Search: ${e.message}`);
        }
    }

    document.getElementById("btnTrackCustOrder").addEventListener("click", () => {
        soundManager.playClick();
        const ord = document.getElementById("custOrderSearchInput").value.trim();
        renderCustomerPortal(ord);
    });

    window.loadCustomerOrderDemo = (ord) => {
        soundManager.playClick();
        document.getElementById("custOrderSearchInput").value = ord;
        renderCustomerPortal(ord);
    };

    // =================================================================
    // SCENE 6: ACTIVITY-BASED COSTING (ABC) ROLLUP
    // =================================================================
    async function renderFinancialRollup(orderId) {
        try {
            const data = await store.getOrderCosting(orderId);

            document.getElementById("abcGrossMarginPct").textContent = `${data.gross_margin_percentage}%`;
            document.getElementById("abcUnitCost").textContent = `$${data.final_cost_per_meter.toFixed(2)} / m`;
            document.getElementById("abcContractPrice").textContent = `$${data.contract_price_per_meter.toFixed(2)} / m`;

            document.getElementById("abcTotalCostVal").textContent = `$${data.total_manufacturing_cost.toLocaleString()}`;
            document.getElementById("abcRevenueVal").textContent = `$${data.revenue.toLocaleString()}`;

            // Waterfall Chart
            const waterfallCont = document.getElementById("waterfallContainer");
            waterfallCont.innerHTML = "";

            const maxAmount = Math.max(...data.cost_waterfall.map(x => x.amount), data.revenue);

            data.cost_waterfall.forEach(item => {
                const row = document.createElement("div");
                row.className = "waterfall-row";

                const widthPct = Math.min(100, Math.max(5, (item.amount / maxAmount) * 100));
                let barClass = "cost";
                if (item.name.includes("Loom")) barClass = "overhead";
                if (item.name.includes("Scrap")) barClass = "scrap";
                if (item.type === "total_cost") barClass = "total";
                if (item.type === "profit" || item.type === "revenue") barClass = "profit";

                row.innerHTML = `
                    <div class="waterfall-label">${item.name}</div>
                    <div class="waterfall-bar-track">
                        <div class="waterfall-bar-val ${barClass}" style="width: ${widthPct}%;">
                            $${item.amount.toLocaleString()}
                        </div>
                    </div>
                `;
                waterfallCont.appendChild(row);
            });
        } catch (e) {
            console.error("Costing Rollup error:", e);
        }
    }

    document.getElementById("costingOrderSelect").addEventListener("change", (e) => {
        soundManager.playClick();
        renderFinancialRollup(e.target.value);
    });
});
