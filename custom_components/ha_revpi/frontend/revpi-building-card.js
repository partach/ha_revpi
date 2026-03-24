import { LitElement, html, css } from "https://unpkg.com/lit?module";

class RevPiBuildingCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _deviceEntities: { type: Array },
      _editingEntity: { type: String },
      _editValue: { type: String },
    };
  }

  constructor() {
    super();
    this._deviceEntities = [];
    this._editingEntity = null;
    this._editValue = "";
  }

  static getConfigElement() {
    return document.createElement("revpi-building-card-editor");
  }

  static getStubConfig() {
    return { device_id: "" };
  }

  setConfig(config) {
    this.config = { ...config };
    this.requestUpdate();
  }

  getCardSize() {
    return 6;
  }

  updated(changedProps) {
    super.updated(changedProps);
    if (changedProps.has("hass")) this._resolveDeviceEntities();
  }

  _resolveDeviceEntities() {
    if (!this.hass || !this.config.device_id) return;
    const reg = this.hass.entities;
    if (!reg) return;
    this._deviceEntities = Object.values(reg)
      .filter((e) => e.device_id === this.config.device_id)
      .map((e) => e.entity_id)
      .sort();
  }

  /* ── helpers ── */

  _st(eid) {
    return this.hass.states[eid];
  }

  _byDomain(d) {
    return this._deviceEntities.filter((e) => e.startsWith(d + "."));
  }

  _shortName(eid) {
    const e = this._st(eid);
    const f = e?.attributes?.friendly_name || "";
    const dn = this._getDeviceName();
    if (dn && f.startsWith(dn + " ")) return f.substring(dn.length + 1);
    return f || eid.split(".")[1]?.replace(/^ha_revpi_/i, "") || eid;
  }

  _getDeviceName() {
    return this.hass.devices?.[this.config.device_id]?.name || null;
  }

  _isBinary(s) {
    const u = s?.toUpperCase();
    return u === "ON" || u === "OFF";
  }

  /* ── inline edit (for number entities) ── */

  _startEdit(eid) {
    const e = this._st(eid);
    this._editingEntity = eid;
    this._editValue = e?.state || "0";
    this.requestUpdate();
    this.updateComplete.then(() => {
      const inp = this.shadowRoot?.querySelector(".edit-input");
      if (inp) { inp.focus(); inp.select(); }
    });
  }

  async _commitEdit() {
    if (!this._editingEntity) return;
    const val = parseFloat(this._editValue);
    if (!isNaN(val)) {
      await this.hass.callService("number", "set_value", {
        entity_id: this._editingEntity, value: val,
      });
    }
    this._editingEntity = null;
    this._editValue = "";
  }

  _cancelEdit() {
    this._editingEntity = null;
    this._editValue = "";
  }

  _editKey(e) {
    if (e.key === "Enter") { e.preventDefault(); this._commitEdit(); }
    else if (e.key === "Escape") { e.preventDefault(); this._cancelEdit(); }
  }

  /* ── service calls ── */

  async _toggleSwitch(eid) {
    const e = this._st(eid);
    if (!e) return;
    const svc = e.state === "on" ? "turn_off" : "turn_on";
    await this.hass.callService("switch", svc, { entity_id: eid });
  }

  async _toggleFan(eid) {
    const e = this._st(eid);
    if (!e) return;
    const svc = e.state === "on" ? "turn_off" : "turn_on";
    await this.hass.callService("fan", svc, { entity_id: eid });
  }

  async _setClimateTemp(eid, delta) {
    const e = this._st(eid);
    if (!e) return;
    const cur = e.attributes.temperature || 21;
    await this.hass.callService("climate", "set_temperature", {
      entity_id: eid, temperature: cur + delta,
    });
  }

  async _setClimateMode(eid, mode) {
    await this.hass.callService("climate", "set_hvac_mode", {
      entity_id: eid, hvac_mode: mode,
    });
  }

  async _setCoverPos(eid, pos) {
    await this.hass.callService("cover", "set_cover_position", {
      entity_id: eid, position: pos,
    });
  }

  /* ── render ── */

  render() {
    if (!this.hass || !this.config) return html``;
    const title = this.config.title || this._getDeviceName() || "Building Device";
    const model = this.hass.devices?.[this.config.device_id]?.model || "Device";

    const climates = this._byDomain("climate");
    const fans = this._byDomain("fan");
    const covers = this._byDomain("cover");
    const switches = this._byDomain("switch");
    const numbers = this._byDomain("number");
    const sensors = this._byDomain("sensor");

    const alarms = sensors.filter((e) => this._isBinary(this._st(e)?.state));
    const analogs = sensors.filter((e) => !this._isBinary(this._st(e)?.state));

    // PID entities
    const pidNums = numbers.filter((e) =>
      e.includes("_pid_") || e.includes("_kp") || e.includes("_ti") || e.includes("_td") || e.includes("setpoint")
    );
    const otherNums = numbers.filter((e) => !pidNums.includes(e));
    const pidSwitch = switches.find((e) => e.includes("pid_enable"));
    const otherSwitches = switches.filter((e) => e !== pidSwitch);
    const pidOutput = analogs.find((e) => e.includes("pid_output"));
    const otherAnalogs = analogs.filter((e) => e !== pidOutput);

    return html`
      <ha-card>
        <div class="header">
          <div class="header-left">
            <ha-icon icon="mdi:office-building-cog-outline"></ha-icon>
            <span class="title">${title}</span>
          </div>
          <span class="badge">${model}</span>
        </div>
        <div class="card-content">
          ${climates.map((e) => this._renderClimate(e))}
          ${fans.length ? this._renderSection("FANS", fans.map((e) => this._renderFan(e))) : ""}
          ${covers.length ? this._renderSection("DAMPERS", covers.map((e) => this._renderCover(e))) : ""}
          ${otherSwitches.length ? this._renderSection("SWITCHES", otherSwitches.map((e) => this._renderSwitch(e))) : ""}
          ${otherNums.length ? this._renderSection("CONTROLS", otherNums.map((e) => this._renderNumber(e))) : ""}
          ${otherAnalogs.length ? this._renderSection("SENSORS", html`<div class="sensor-grid">${otherAnalogs.map((e) => this._renderSensor(e))}</div>`) : ""}
          ${alarms.length ? this._renderSection("ALARMS", html`<div class="alarm-grid">${alarms.map((e) => this._renderAlarm(e))}</div>`) : ""}
          ${pidNums.length || pidSwitch || pidOutput ? this._renderPID(pidNums, pidSwitch, pidOutput) : ""}
        </div>
      </ha-card>
    `;
  }

  _renderSection(label, content) {
    return html`<div class="section"><div class="section-label">${label}</div>${content}</div>`;
  }

  /* ── climate (interactive) ── */

  _renderClimate(eid) {
    const e = this._st(eid);
    if (!e) return html``;
    const cur = e.attributes.current_temperature;
    const tgt = e.attributes.temperature;
    const mode = e.state;
    const action = e.attributes.hvac_action || "";
    const unit = e.attributes.temperature_unit || "°C";
    const modes = e.attributes.hvac_modes || [];

    return html`
      <div class="section">
        <div class="section-label">CLIMATE</div>
        <div class="climate-card">
          <div class="climate-row">
            <div class="climate-temps">
              ${cur != null ? html`
                <div class="temp-block">
                  <span class="temp-label">Current</span>
                  <span class="temp-value">${cur}${unit}</span>
                </div>` : ""}
              ${tgt != null ? html`
                <div class="temp-block">
                  <span class="temp-label">Target</span>
                  <div class="temp-adjust">
                    <button class="adj-btn" @click=${() => this._setClimateTemp(eid, -0.5)}>−</button>
                    <span class="temp-value target">${tgt}${unit}</span>
                    <button class="adj-btn" @click=${() => this._setClimateTemp(eid, 0.5)}>+</button>
                  </div>
                </div>` : ""}
            </div>
            <div class="climate-right">
              ${action ? html`<span class="action action-${action}">${action}</span>` : ""}
              <div class="mode-buttons">
                ${modes.map((m) => html`
                  <button class="mode-btn ${m === mode ? "active" : ""}" @click=${() => this._setClimateMode(eid, m)}>
                    <ha-icon icon="${this._modeIcon(m)}"></ha-icon>
                  </button>
                `)}
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  _modeIcon(mode) {
    const m = { off: "mdi:power", heat: "mdi:fire", cool: "mdi:snowflake", auto: "mdi:autorenew", heat_cool: "mdi:autorenew", fan_only: "mdi:fan" };
    return m[mode] || "mdi:thermostat";
  }

  /* ── fan (toggle) ── */

  _renderFan(eid) {
    const e = this._st(eid);
    if (!e) return html``;
    const isOn = e.state === "on";
    const speed = e.attributes.percentage;
    return html`
      <div class="control-item ${isOn ? "on" : "off"}" @click=${() => this._toggleFan(eid)}>
        <ha-icon icon="mdi:fan" class="${isOn ? "spin" : ""}"></ha-icon>
        <span class="name">${this._shortName(eid)}</span>
        <span class="val">${isOn ? (speed != null ? speed + "%" : "ON") : "OFF"}</span>
      </div>
    `;
  }

  /* ── cover (slider) ── */

  _renderCover(eid) {
    const e = this._st(eid);
    if (!e) return html``;
    const pos = e.attributes.current_position;
    return html`
      <div class="bar-item">
        <div class="bar-header">
          <ha-icon icon="mdi:valve"></ha-icon>
          <span class="name">${this._shortName(eid)}</span>
          <span class="val">${pos != null ? pos + "%" : e.state}</span>
        </div>
        ${pos != null ? html`
          <input type="range" class="slider" min="0" max="100" .value=${String(pos)}
            @change=${(ev) => this._setCoverPos(eid, parseInt(ev.target.value))} />
        ` : ""}
      </div>
    `;
  }

  /* ── switch (toggle) ── */

  _renderSwitch(eid) {
    const e = this._st(eid);
    if (!e) return html``;
    const isOn = e.state === "on";
    return html`
      <div class="control-item ${isOn ? "on" : "off"}" @click=${() => this._toggleSwitch(eid)}>
        <ha-icon icon="mdi:toggle-switch${isOn ? "" : "-off-outline"}"></ha-icon>
        <span class="name">${this._shortName(eid)}</span>
        <span class="val">${isOn ? "ON" : "OFF"}</span>
      </div>
    `;
  }

  /* ── number (click-to-edit) ── */

  _renderNumber(eid) {
    const e = this._st(eid);
    if (!e) return html``;
    const val = parseFloat(e.state);
    const unit = e.attributes.unit_of_measurement || "";
    const min = e.attributes.min ?? 0;
    const max = e.attributes.max ?? 100;
    const pct = max > min ? ((val - min) / (max - min)) * 100 : 0;
    const editing = this._editingEntity === eid;

    return html`
      <div class="bar-item">
        <div class="bar-header">
          <ha-icon icon="mdi:tune-vertical"></ha-icon>
          <span class="name">${this._shortName(eid)}</span>
          ${editing ? html`
            <input class="edit-input" type="number" .value=${this._editValue}
              min=${min} max=${max} step="any"
              @input=${(ev) => (this._editValue = ev.target.value)}
              @keydown=${(ev) => this._editKey(ev)}
              @blur=${() => this._commitEdit()} />
          ` : html`
            <span class="val clickable" @click=${() => this._startEdit(eid)}>
              ${isNaN(val) ? e.state : val}${unit}
            </span>
          `}
        </div>
        <div class="bar-track"><div class="bar-fill accent" style="width:${pct}%"></div></div>
      </div>
    `;
  }

  /* ── sensor ── */

  _renderSensor(eid) {
    const e = this._st(eid);
    if (!e) return html``;
    const unit = e.attributes.unit_of_measurement || "";
    const icon = e.attributes.icon || "mdi:gauge";
    return html`
      <div class="sensor-item">
        <ha-icon icon="${icon}"></ha-icon>
        <span class="name">${this._shortName(eid)}</span>
        <span class="val">${e.state}${unit ? " " + unit : ""}</span>
      </div>
    `;
  }

  /* ── alarm ── */

  _renderAlarm(eid) {
    const e = this._st(eid);
    if (!e) return html``;
    const isOn = e.state?.toUpperCase() === "ON";
    return html`
      <div class="alarm-item ${isOn ? "active" : "normal"}">
        <ha-icon icon="${isOn ? "mdi:alert-circle" : "mdi:check-circle"}"></ha-icon>
        <span class="name">${this._shortName(eid)}</span>
        <span class="status">${isOn ? "ALARM" : "OK"}</span>
      </div>
    `;
  }

  /* ── PID engineering view ── */

  _renderPID(paramEids, enableEid, outputEid) {
    const enableSt = enableEid ? this._st(enableEid) : null;
    const isEnabled = enableSt?.state === "on";
    const outputSt = outputEid ? this._st(outputEid) : null;
    const outputVal = outputSt ? parseFloat(outputSt.state) : null;

    // Find specific params
    const find = (k) => paramEids.find((e) => e.includes(k));
    const spEid = find("setpoint");
    const kpEid = find("_kp");
    const tiEid = find("_ti");
    const tdEid = find("_td");
    const oMinEid = find("output_min");
    const oMaxEid = find("output_max");
    const sampleEid = find("sample_interval");

    const sp = spEid ? this._st(spEid) : null;
    const kp = kpEid ? this._st(kpEid) : null;
    const ti = tiEid ? this._st(tiEid) : null;
    const td = tdEid ? this._st(tdEid) : null;
    const oMin = oMinEid ? this._st(oMinEid) : null;
    const oMax = oMaxEid ? this._st(oMaxEid) : null;

    // Try to find the process value:
    // 1. Check for a standalone temperature sensor on this device
    // 2. Fall back to the climate entity's current_temperature attribute
    let pvEid = this._deviceEntities.find((e) => {
      if (!e.startsWith("sensor.")) return false;
      const st = this._st(e);
      return st?.attributes?.device_class === "temperature" ||
             e.includes("current_temperature") || e.includes("supply_temp");
    });
    let pvSt = pvEid ? this._st(pvEid) : null;
    let pvVal = pvSt?.state;
    let pvUnit = pvSt?.attributes?.unit_of_measurement || "";
    let pvName = pvEid ? this._shortName(pvEid) : "";

    // Fall back to climate entity's current_temperature
    if (!pvEid) {
      const climateEid = this._deviceEntities.find((e) => e.startsWith("climate."));
      const climateSt = climateEid ? this._st(climateEid) : null;
      if (climateSt?.attributes?.current_temperature != null) {
        pvVal = String(climateSt.attributes.current_temperature);
        pvUnit = climateSt.attributes.temperature_unit || "°C";
        pvName = "Current Temp";
        pvEid = climateEid; // for display purposes
      }
    }

    // Try to find the output actuator (heating_valve, cooling_valve, damper)
    // Check sensor, cover, and number domains
    const actuatorEid = this._deviceEntities.find((e) =>
      (e.startsWith("sensor.") || e.startsWith("cover.") || e.startsWith("number.")) &&
      (e.includes("heating_valve") || e.includes("cooling_valve") || e.includes("damper")) &&
      !e.includes("pid_") && !e.includes("alarm")
    );
    const actuatorSt = actuatorEid ? this._st(actuatorEid) : null;
    const actuatorPos = actuatorSt
      ? (actuatorSt.attributes?.current_position ?? parseFloat(actuatorSt.state))
      : null;

    return html`
      <div class="section">
        <div class="section-label">PID CONTROLLER</div>
        <div class="pid-card">
          <!-- Enable toggle row -->
          ${enableEid ? html`
            <div class="pid-enable-row">
              <span class="pid-enable-label">Control Loop</span>
              <button class="pid-toggle ${isEnabled ? "on" : "off"}"
                @click=${() => this._toggleSwitch(enableEid)}>
                ${isEnabled ? "RUNNING" : "STOPPED"}
              </button>
            </div>
          ` : ""}

          <!-- Engineering diagram -->
          <div class="pid-diagram">
            <!-- Input (PV) -->
            <div class="pid-block pv-block">
              <div class="pid-block-label">Process Value</div>
              <div class="pid-block-value">
                ${pvVal != null ? html`${pvVal}${pvUnit}` : "—"}
              </div>
              ${pvName ? html`<div class="pid-block-io">${pvName}</div>` : ""}
            </div>

            <div class="pid-arrow">→</div>

            <!-- PID block -->
            <div class="pid-block ctrl-block ${isEnabled ? "active" : ""}">
              <div class="pid-block-label">PID</div>
              <div class="pid-inner-grid">
                ${sp ? html`<div class="pid-p"><span class="pl">SP</span><span class="pv clickable" @click=${() => this._startEdit(spEid)}>${sp.state}${sp.attributes.unit_of_measurement || ""}</span></div>` : ""}
                ${kp ? html`<div class="pid-p"><span class="pl">Kp</span><span class="pv clickable" @click=${() => this._startEdit(kpEid)}>${kp.state}</span></div>` : ""}
                ${ti ? html`<div class="pid-p"><span class="pl">Ti</span><span class="pv clickable" @click=${() => this._startEdit(tiEid)}>${ti.state}s</span></div>` : ""}
                ${td ? html`<div class="pid-p"><span class="pl">Td</span><span class="pv clickable" @click=${() => this._startEdit(tdEid)}>${td.state}s</span></div>` : ""}
              </div>
              ${outputVal != null ? html`
                <div class="pid-output-bar">
                  <div class="pid-output-fill" style="width:${Math.min(100, Math.max(0, outputVal))}%"></div>
                </div>
                <div class="pid-output-val">Output: ${outputVal.toFixed(1)}%</div>
              ` : ""}
            </div>

            <div class="pid-arrow">→</div>

            <!-- Output (Actuator) -->
            <div class="pid-block out-block">
              <div class="pid-block-label">Actuator</div>
              <div class="pid-block-value">
                ${actuatorPos != null ? html`${actuatorPos}%` : "—"}
              </div>
              ${actuatorEid ? html`<div class="pid-block-io">${this._shortName(actuatorEid)}</div>` : ""}
            </div>
          </div>

          <!-- Output limits -->
          ${oMin || oMax ? html`
            <div class="pid-limits">
              ${oMin ? html`<span class="pid-limit">Min: ${oMin.state}%</span>` : ""}
              ${oMax ? html`<span class="pid-limit">Max: ${oMax.state}%</span>` : ""}
            </div>
          ` : ""}

          <!-- Edit overlay for PID params -->
          ${this._editingEntity && paramEids.includes(this._editingEntity) ? html`
            <div class="pid-edit-overlay">
              <label>${this._shortName(this._editingEntity)}</label>
              <input class="edit-input" type="number" step="any"
                .value=${this._editValue}
                @input=${(ev) => (this._editValue = ev.target.value)}
                @keydown=${(ev) => this._editKey(ev)}
                @blur=${() => this._commitEdit()} />
            </div>
          ` : ""}
        </div>
      </div>
    `;
  }

  /* ── styles ── */

  static get styles() {
    return css`
      :host {
        --accent: var(--primary-color, #03a9f4);
        --green: #4caf50;
        --red: #f44336;
        --orange: #ff9800;
        --text1: var(--primary-text-color, #212121);
        --text2: var(--secondary-text-color, #727272);
        --divider: var(--divider-color, rgba(0,0,0,0.12));
      }
      ha-card { overflow: hidden; }

      .header { display:flex; justify-content:space-between; align-items:center; padding:16px 16px 8px; }
      .header-left { display:flex; align-items:center; gap:8px; }
      .header-left ha-icon { color:var(--accent); --mdc-icon-size:24px; }
      .title { font-size:1.1em; font-weight:500; color:var(--text1); }
      .badge { font-size:0.7em; font-weight:600; text-transform:uppercase; padding:2px 8px; border-radius:10px; background:var(--accent); color:white; }
      .card-content { padding:0 16px 16px; }

      .section { margin-top:12px; }
      .section-label { font-size:0.7em; font-weight:600; color:var(--text2); letter-spacing:1px; margin-bottom:8px; }

      /* climate */
      .climate-card { background:var(--divider); border-radius:12px; padding:12px; }
      .climate-row { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; }
      .climate-temps { display:flex; gap:24px; }
      .temp-block { display:flex; flex-direction:column; gap:2px; }
      .temp-label { font-size:0.7em; color:var(--text2); text-transform:uppercase; letter-spacing:0.5px; }
      .temp-value { font-size:1.4em; font-weight:600; color:var(--text1); }
      .temp-value.target { color:var(--accent); }
      .temp-adjust { display:flex; align-items:center; gap:4px; }
      .adj-btn { width:28px; height:28px; border:none; border-radius:50%; background:var(--accent); color:white; font-size:1.1em; cursor:pointer; display:flex; align-items:center; justify-content:center; line-height:1; }
      .adj-btn:hover { filter:brightness(1.15); }
      .climate-right { display:flex; flex-direction:column; align-items:flex-end; gap:6px; }
      .action { font-size:0.7em; font-weight:600; text-transform:uppercase; padding:2px 8px; border-radius:8px; color:white; }
      .action-heating { background:var(--orange); }
      .action-cooling { background:var(--accent); }
      .action-idle { background:var(--text2); }
      .action-off { background:var(--text2); }
      .mode-buttons { display:flex; gap:4px; }
      .mode-btn { width:32px; height:32px; border:1px solid var(--divider); border-radius:8px; background:transparent; cursor:pointer; display:flex; align-items:center; justify-content:center; }
      .mode-btn ha-icon { --mdc-icon-size:18px; color:var(--text2); }
      .mode-btn.active { background:var(--accent); border-color:var(--accent); }
      .mode-btn.active ha-icon { color:white; }

      /* fan/switch grid */
      .control-item { display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:10px; background:var(--divider); cursor:pointer; margin:0 8px 8px 0; transition:background 0.2s; }
      .control-item:hover { filter:brightness(0.95); }
      .control-item.on { background:color-mix(in srgb, var(--green) 18%, transparent); }
      .control-item ha-icon { --mdc-icon-size:22px; color:var(--text2); }
      .control-item.on ha-icon { color:var(--green); }
      .control-item .name { font-size:0.85em; color:var(--text1); }
      .control-item .val { font-size:0.75em; font-weight:600; color:var(--text2); }
      .control-item.on .val { color:var(--green); }
      .spin { animation:spin 1.5s linear infinite; }
      @keyframes spin { 100% { transform:rotate(360deg); } }

      /* bar items (covers, numbers) */
      .bar-item { margin-bottom:10px; }
      .bar-header { display:flex; align-items:center; gap:8px; margin-bottom:4px; }
      .bar-header ha-icon { --mdc-icon-size:18px; color:var(--text2); }
      .bar-header .name { flex:1; font-size:0.85em; color:var(--text1); }
      .bar-header .val { font-size:0.85em; font-weight:600; color:var(--text1); }
      .bar-track { height:6px; border-radius:3px; background:var(--divider); overflow:hidden; }
      .bar-fill { height:100%; border-radius:3px; background:var(--green); transition:width 0.5s; }
      .bar-fill.accent { background:var(--accent); }
      .clickable { cursor:pointer; text-decoration:underline dotted; }
      .edit-input { width:70px; padding:2px 6px; border:1px solid var(--accent); border-radius:4px; font-size:0.85em; background:var(--ha-card-background, white); color:var(--text1); }
      input[type=range].slider { width:100%; margin:4px 0 0; cursor:pointer; accent-color:var(--green); }

      /* sensors */
      .sensor-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(140px,1fr)); gap:8px; }
      .sensor-item { display:flex; align-items:center; gap:6px; padding:8px 10px; border-radius:8px; background:var(--divider); }
      .sensor-item ha-icon { --mdc-icon-size:18px; color:var(--text2); }
      .sensor-item .name { flex:1; font-size:0.8em; color:var(--text1); }
      .sensor-item .val { font-size:0.85em; font-weight:600; white-space:nowrap; }

      /* alarms */
      .alarm-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(140px,1fr)); gap:8px; }
      .alarm-item { display:flex; align-items:center; gap:6px; padding:8px 10px; border-radius:8px; }
      .alarm-item.normal { background:color-mix(in srgb, var(--green) 12%, transparent); }
      .alarm-item.active { background:color-mix(in srgb, var(--red) 15%, transparent); animation:pulse 2s infinite; }
      @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.7;} }
      .alarm-item ha-icon { --mdc-icon-size:18px; }
      .alarm-item.normal ha-icon { color:var(--green); }
      .alarm-item.active ha-icon { color:var(--red); }
      .alarm-item .name { flex:1; font-size:0.8em; }
      .alarm-item .status { font-size:0.7em; font-weight:700; }
      .alarm-item.normal .status { color:var(--green); }
      .alarm-item.active .status { color:var(--red); }

      /* PID engineering view */
      .pid-card { background:var(--divider); border-radius:12px; padding:12px; position:relative; }
      .pid-enable-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
      .pid-enable-label { font-size:0.85em; font-weight:500; color:var(--text1); }
      .pid-toggle { padding:4px 14px; border:none; border-radius:8px; font-size:0.75em; font-weight:700; cursor:pointer; letter-spacing:0.5px; }
      .pid-toggle.on { background:var(--green); color:white; }
      .pid-toggle.off { background:var(--text2); color:white; }

      .pid-diagram { display:flex; align-items:center; gap:6px; justify-content:center; flex-wrap:wrap; }
      .pid-arrow { font-size:1.4em; color:var(--text2); font-weight:bold; }

      .pid-block { border-radius:10px; padding:10px; text-align:center; min-width:90px; flex:1; }
      .pid-block-label { font-size:0.65em; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; color:var(--text2); margin-bottom:4px; }
      .pid-block-value { font-size:1.2em; font-weight:600; color:var(--text1); }
      .pid-block-io { font-size:0.65em; color:var(--text2); margin-top:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

      .pv-block { background:color-mix(in srgb, var(--accent) 12%, transparent); border:1px solid color-mix(in srgb, var(--accent) 30%, transparent); }
      .out-block { background:color-mix(in srgb, var(--orange) 12%, transparent); border:1px solid color-mix(in srgb, var(--orange) 30%, transparent); }
      .ctrl-block { background:rgba(255,255,255,0.06); border:2px solid var(--text2); flex:1.5; }
      .ctrl-block.active { border-color:var(--green); }

      .pid-inner-grid { display:grid; grid-template-columns:1fr 1fr; gap:4px 12px; margin:6px 0; }
      .pid-p { display:flex; justify-content:space-between; align-items:center; }
      .pl { font-size:0.7em; font-weight:600; color:var(--text2); }
      .pv { font-size:0.85em; font-weight:600; color:var(--text1); }

      .pid-output-bar { height:6px; border-radius:3px; background:rgba(0,0,0,0.15); margin:6px 0 2px; overflow:hidden; }
      .pid-output-fill { height:100%; border-radius:3px; background:var(--green); transition:width 0.5s; }
      .pid-output-val { font-size:0.7em; color:var(--text2); }

      .pid-limits { display:flex; gap:16px; justify-content:center; margin-top:8px; }
      .pid-limit { font-size:0.7em; color:var(--text2); }

      .pid-edit-overlay { position:absolute; bottom:8px; left:8px; right:8px; background:var(--ha-card-background, white); border:1px solid var(--accent); border-radius:8px; padding:8px 12px; display:flex; align-items:center; gap:8px; box-shadow:0 2px 8px rgba(0,0,0,0.15); z-index:1; }
      .pid-edit-overlay label { font-size:0.8em; font-weight:500; color:var(--text1); flex:1; }
      .pid-edit-overlay .edit-input { width:80px; }
    `;
  }
}

/* ── Card editor ── */

class RevPiBuildingCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, _config: { type: Object } };
  }

  setConfig(config) { this._config = { ...config }; }

  _getDevices() {
    if (!this.hass) return [];
    return Object.values(this.hass.devices || {}).filter((d) =>
      (d.identifiers || []).some(([domain, id]) => domain === "ha_revpi" && id.includes("_bld"))
    );
  }

  _changed(field, ev) {
    this._config = { ...this._config, [field]: ev.target.value };
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } }));
  }

  render() {
    if (!this.hass || !this._config) return html``;
    const devices = this._getDevices();
    return html`
      <div class="editor">
        <label>Building Device</label>
        <select .value=${this._config.device_id || ""} @change=${(e) => this._changed("device_id", e)}>
          <option value="">Select a building device...</option>
          ${devices.map((d) => html`<option value=${d.id} ?selected=${d.id === this._config.device_id}>${d.name} (${d.model || "Device"})</option>`)}
        </select>
        <label>Title (optional)</label>
        <input type="text" .value=${this._config.title || ""} placeholder="Auto-detect from device" @input=${(e) => this._changed("title", e)} />
      </div>
    `;
  }

  static get styles() {
    return css`
      .editor { display:flex; flex-direction:column; gap:8px; padding:16px; }
      label { font-weight:500; font-size:0.9em; }
      select, input { padding:8px; border:1px solid var(--divider-color, #ccc); border-radius:4px; font-size:0.9em; }
    `;
  }
}

customElements.define("revpi-building-card", RevPiBuildingCard);
customElements.define("revpi-building-card-editor", RevPiBuildingCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "revpi-building-card",
  name: "RevPi Building Device Card",
  description: "Interactive building device card with climate control, fans, dampers, valves, alarms, and PID engineering view.",
  preview: true,
});
