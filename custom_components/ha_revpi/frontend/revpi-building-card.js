import { LitElement, html, css } from "https://unpkg.com/lit?module";

class RevPiBuildingCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _deviceEntities: { type: Array },
    };
  }

  constructor() {
    super();
    this._deviceEntities = [];
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
    if (changedProps.has("hass")) {
      this._resolveDeviceEntities();
    }
  }

  _resolveDeviceEntities() {
    if (!this.hass || !this.config.device_id) return;
    const entityReg = this.hass.entities;
    if (!entityReg) return;
    this._deviceEntities = Object.values(entityReg)
      .filter((e) => e.device_id === this.config.device_id)
      .map((e) => e.entity_id)
      .sort();
  }

  /* ── Entity helpers ── */

  _getDeviceName() {
    if (!this.hass || !this.config.device_id) return null;
    const device = this.hass.devices?.[this.config.device_id];
    return device?.name || null;
  }

  _getShortName(entityId) {
    const entity = this.hass.states[entityId];
    const friendly = entity?.attributes?.friendly_name || "";
    const deviceName = this._getDeviceName();
    if (deviceName && friendly.startsWith(deviceName + " ")) {
      return friendly.substring(deviceName.length + 1);
    }
    if (friendly) return friendly;
    const tail = entityId.split(".")[1] || entityId;
    return tail.replace(/^ha_revpi_/i, "").replace(/_sensor$/, "");
  }

  _getEntitiesByDomain(domain) {
    return this._deviceEntities.filter((eid) => eid.startsWith(domain + "."));
  }

  _getState(entityId) {
    return this.hass.states[entityId];
  }

  /* ── Render ── */

  render() {
    if (!this.hass || !this.config) return html``;

    const title =
      this.config.title || this._getDeviceName() || "Building Device";
    const climates = this._getEntitiesByDomain("climate");
    const fans = this._getEntitiesByDomain("fan");
    const covers = this._getEntitiesByDomain("cover");
    const numbers = this._getEntitiesByDomain("number");
    const sensors = this._getEntitiesByDomain("sensor");
    const switches = this._getEntitiesByDomain("switch");

    // Separate alarm sensors from analog sensors
    const alarmSensors = sensors.filter((eid) => {
      const entity = this._getState(eid);
      const s = entity?.state?.toUpperCase();
      return s === "ON" || s === "OFF";
    });
    const analogSensors = sensors.filter((eid) => {
      const entity = this._getState(eid);
      const s = entity?.state?.toUpperCase();
      return s !== "ON" && s !== "OFF";
    });

    // Find PID-related number entities
    const pidEntities = numbers.filter(
      (eid) =>
        eid.includes("_kp") ||
        eid.includes("_ti") ||
        eid.includes("_td") ||
        eid.includes("_setpoint") ||
        eid.includes("pid_")
    );
    const otherNumbers = numbers.filter((eid) => !pidEntities.includes(eid));

    return html`
      <ha-card>
        ${this._renderHeader(title)}
        <div class="card-content">
          ${climates.length > 0
            ? this._renderClimateSection(climates)
            : ""}
          ${fans.length > 0 ? this._renderFanSection(fans) : ""}
          ${covers.length > 0 ? this._renderCoverSection(covers) : ""}
          ${otherNumbers.length > 0
            ? this._renderNumberSection(otherNumbers)
            : ""}
          ${analogSensors.length > 0
            ? this._renderAnalogSection(analogSensors)
            : ""}
          ${alarmSensors.length > 0
            ? this._renderAlarmSection(alarmSensors)
            : ""}
          ${pidEntities.length > 0
            ? this._renderPIDSection(pidEntities)
            : ""}
        </div>
      </ha-card>
    `;
  }

  /* ── Header ── */

  _renderHeader(title) {
    const model =
      this.hass.devices?.[this.config.device_id]?.model || "Device";
    return html`
      <div class="header">
        <div class="header-left">
          <ha-icon icon="mdi:office-building-cog-outline"></ha-icon>
          <span class="title">${title}</span>
        </div>
        <span class="badge">${model}</span>
      </div>
    `;
  }

  /* ── Climate section ── */

  _renderClimateSection(entities) {
    return html`
      <div class="section">
        <div class="section-label">CLIMATE</div>
        ${entities.map((eid) => this._renderClimate(eid))}
      </div>
    `;
  }

  _renderClimate(eid) {
    const entity = this._getState(eid);
    if (!entity) return html``;
    const name = this._getShortName(eid);
    const current = entity.attributes.current_temperature;
    const target = entity.attributes.temperature;
    const mode = entity.state;
    const unit = entity.attributes.temperature_unit || "°C";

    return html`
      <div class="climate-card">
        <div class="climate-header">
          <ha-icon icon="mdi:thermostat"></ha-icon>
          <span class="name">${name}</span>
          <span class="mode mode-${mode}">${mode}</span>
        </div>
        <div class="climate-temps">
          ${current != null
            ? html`
                <div class="temp-block">
                  <span class="temp-label">Current</span>
                  <span class="temp-value">${current}${unit}</span>
                </div>
              `
            : ""}
          ${target != null
            ? html`
                <div class="temp-block">
                  <span class="temp-label">Target</span>
                  <span class="temp-value target">${target}${unit}</span>
                </div>
              `
            : ""}
        </div>
      </div>
    `;
  }

  /* ── Fan section ── */

  _renderFanSection(entities) {
    return html`
      <div class="section">
        <div class="section-label">FANS</div>
        <div class="item-grid">
          ${entities.map((eid) => this._renderFan(eid))}
        </div>
      </div>
    `;
  }

  _renderFan(eid) {
    const entity = this._getState(eid);
    if (!entity) return html``;
    const name = this._getShortName(eid);
    const isOn = entity.state === "on";
    const speed = entity.attributes.percentage;

    return html`
      <div
        class="control-item ${isOn ? "on" : "off"}"
        @click=${() => this._toggleFan(eid)}
      >
        <ha-icon
          icon="mdi:fan"
          class="fan-icon ${isOn ? "spinning" : ""}"
        ></ha-icon>
        <span class="name">${name}</span>
        <span class="value">${isOn ? (speed != null ? speed + "%" : "ON") : "OFF"}</span>
      </div>
    `;
  }

  async _toggleFan(entityId) {
    const entity = this._getState(entityId);
    if (!entity) return;
    const service = entity.state === "on" ? "turn_off" : "turn_on";
    await this.hass.callService("fan", service, { entity_id: entityId });
  }

  /* ── Cover / Damper section ── */

  _renderCoverSection(entities) {
    return html`
      <div class="section">
        <div class="section-label">DAMPERS</div>
        ${entities.map((eid) => this._renderCover(eid))}
      </div>
    `;
  }

  _renderCover(eid) {
    const entity = this._getState(eid);
    if (!entity) return html``;
    const name = this._getShortName(eid);
    const pos = entity.attributes.current_position;

    return html`
      <div class="bar-item">
        <div class="bar-header">
          <ha-icon icon="mdi:valve"></ha-icon>
          <span class="name">${name}</span>
          <span class="value">${pos != null ? pos + "%" : entity.state}</span>
        </div>
        ${pos != null
          ? html`
              <div class="bar-track">
                <div class="bar-fill" style="width: ${pos}%"></div>
              </div>
            `
          : ""}
      </div>
    `;
  }

  /* ── Number / Valve section ── */

  _renderNumberSection(entities) {
    return html`
      <div class="section">
        <div class="section-label">CONTROLS</div>
        ${entities.map((eid) => this._renderNumber(eid))}
      </div>
    `;
  }

  _renderNumber(eid) {
    const entity = this._getState(eid);
    if (!entity) return html``;
    const name = this._getShortName(eid);
    const val = parseFloat(entity.state);
    const unit = entity.attributes.unit_of_measurement || "";
    const min = entity.attributes.min ?? 0;
    const max = entity.attributes.max ?? 100;
    const pct = max > min ? ((val - min) / (max - min)) * 100 : 0;

    return html`
      <div class="bar-item">
        <div class="bar-header">
          <ha-icon icon="mdi:tune-vertical"></ha-icon>
          <span class="name">${name}</span>
          <span class="value">${isNaN(val) ? entity.state : val}${unit}</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill accent" style="width: ${pct}%"></div>
        </div>
      </div>
    `;
  }

  /* ── Analog sensors section ── */

  _renderAnalogSection(entities) {
    return html`
      <div class="section">
        <div class="section-label">SENSORS</div>
        <div class="sensor-grid">
          ${entities.map((eid) => this._renderAnalogSensor(eid))}
        </div>
      </div>
    `;
  }

  _renderAnalogSensor(eid) {
    const entity = this._getState(eid);
    if (!entity) return html``;
    const name = this._getShortName(eid);
    const unit = entity.attributes.unit_of_measurement || "";
    const icon = entity.attributes.icon || "mdi:gauge";

    return html`
      <div class="sensor-item">
        <ha-icon icon="${icon}"></ha-icon>
        <span class="name">${name}</span>
        <span class="value">${entity.state}${unit ? " " + unit : ""}</span>
      </div>
    `;
  }

  /* ── Alarm section ── */

  _renderAlarmSection(entities) {
    return html`
      <div class="section">
        <div class="section-label">ALARMS</div>
        <div class="alarm-grid">
          ${entities.map((eid) => this._renderAlarm(eid))}
        </div>
      </div>
    `;
  }

  _renderAlarm(eid) {
    const entity = this._getState(eid);
    if (!entity) return html``;
    const name = this._getShortName(eid);
    const isOn = entity.state?.toUpperCase() === "ON";

    return html`
      <div class="alarm-item ${isOn ? "active" : "normal"}">
        <ha-icon
          icon="${isOn ? "mdi:alert-circle" : "mdi:check-circle"}"
        ></ha-icon>
        <span class="name">${name}</span>
        <span class="status">${isOn ? "ALARM" : "OK"}</span>
      </div>
    `;
  }

  /* ── PID section ── */

  _renderPIDSection(entities) {
    // Group: find setpoint, kp, ti, td, and any pid output sensors
    const setpointEid = entities.find((e) => e.includes("setpoint"));
    const kpEid = entities.find((e) => e.includes("_kp"));
    const tiEid = entities.find((e) => e.includes("_ti"));
    const tdEid = entities.find((e) => e.includes("_td"));

    const setpoint = setpointEid ? this._getState(setpointEid) : null;
    const kp = kpEid ? this._getState(kpEid) : null;
    const ti = tiEid ? this._getState(tiEid) : null;
    const td = tdEid ? this._getState(tdEid) : null;

    return html`
      <div class="section">
        <div class="section-label">PID CONTROLLER</div>
        <div class="pid-card">
          <div class="pid-params">
            ${setpoint
              ? html`
                  <div class="pid-param highlight">
                    <span class="pid-label">Setpoint</span>
                    <span class="pid-value"
                      >${setpoint.state}${setpoint.attributes
                        .unit_of_measurement || ""}</span
                    >
                  </div>
                `
              : ""}
            ${kp
              ? html`
                  <div class="pid-param">
                    <span class="pid-label">Kp</span>
                    <span class="pid-value">${kp.state}</span>
                  </div>
                `
              : ""}
            ${ti
              ? html`
                  <div class="pid-param">
                    <span class="pid-label">Ti</span>
                    <span class="pid-value">${ti.state}s</span>
                  </div>
                `
              : ""}
            ${td
              ? html`
                  <div class="pid-param">
                    <span class="pid-label">Td</span>
                    <span class="pid-value">${td.state}s</span>
                  </div>
                `
              : ""}
          </div>
        </div>
      </div>
    `;
  }

  /* ── Styles ── */

  static get styles() {
    return css`
      :host {
        --card-bg: var(--ha-card-background, var(--card-background-color, #fff));
        --text-primary: var(--primary-text-color, #212121);
        --text-secondary: var(--secondary-text-color, #727272);
        --accent: var(--primary-color, #03a9f4);
        --green: #4caf50;
        --red: #f44336;
        --orange: #ff9800;
        --divider: var(--divider-color, rgba(0, 0, 0, 0.12));
      }

      ha-card {
        overflow: hidden;
      }

      .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 16px 8px;
      }

      .header-left {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .header-left ha-icon {
        color: var(--accent);
        --mdc-icon-size: 24px;
      }

      .title {
        font-size: 1.1em;
        font-weight: 500;
        color: var(--text-primary);
      }

      .badge {
        font-size: 0.7em;
        font-weight: 600;
        text-transform: uppercase;
        padding: 2px 8px;
        border-radius: 10px;
        background: var(--accent);
        color: white;
        letter-spacing: 0.5px;
      }

      .card-content {
        padding: 0 16px 16px;
      }

      .section {
        margin-top: 12px;
      }

      .section-label {
        font-size: 0.7em;
        font-weight: 600;
        color: var(--text-secondary);
        letter-spacing: 1px;
        margin-bottom: 8px;
        text-transform: uppercase;
      }

      /* ── Climate ── */

      .climate-card {
        background: var(--divider);
        border-radius: 12px;
        padding: 12px;
      }

      .climate-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
      }

      .climate-header ha-icon {
        color: var(--orange);
        --mdc-icon-size: 20px;
      }

      .climate-header .name {
        flex: 1;
        font-weight: 500;
      }

      .mode {
        font-size: 0.75em;
        font-weight: 600;
        text-transform: uppercase;
        padding: 2px 8px;
        border-radius: 8px;
        background: var(--text-secondary);
        color: white;
      }

      .mode-heat {
        background: var(--orange);
      }
      .mode-cool {
        background: var(--accent);
      }
      .mode-heat_cool,
      .mode-auto {
        background: var(--green);
      }
      .mode-off {
        background: var(--text-secondary);
      }

      .climate-temps {
        display: flex;
        gap: 24px;
      }

      .temp-block {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .temp-label {
        font-size: 0.7em;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .temp-value {
        font-size: 1.4em;
        font-weight: 600;
        color: var(--text-primary);
      }

      .temp-value.target {
        color: var(--accent);
      }

      /* ── Fans / Controls grid ── */

      .item-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        gap: 8px;
      }

      .control-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        padding: 12px 8px;
        border-radius: 12px;
        background: var(--divider);
        cursor: pointer;
        transition: background 0.2s;
      }

      .control-item:hover {
        filter: brightness(0.95);
      }

      .control-item.on {
        background: color-mix(in srgb, var(--green) 15%, transparent);
      }

      .control-item ha-icon {
        --mdc-icon-size: 28px;
        color: var(--text-secondary);
      }

      .control-item.on ha-icon {
        color: var(--green);
      }

      .fan-icon.spinning {
        animation: spin 1.5s linear infinite;
      }

      @keyframes spin {
        100% {
          transform: rotate(360deg);
        }
      }

      .control-item .name {
        font-size: 0.8em;
        text-align: center;
        color: var(--text-primary);
      }

      .control-item .value {
        font-size: 0.75em;
        font-weight: 600;
        color: var(--text-secondary);
      }

      .control-item.on .value {
        color: var(--green);
      }

      /* ── Bar items (covers, numbers) ── */

      .bar-item {
        margin-bottom: 8px;
      }

      .bar-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;
      }

      .bar-header ha-icon {
        --mdc-icon-size: 18px;
        color: var(--text-secondary);
      }

      .bar-header .name {
        flex: 1;
        font-size: 0.85em;
        color: var(--text-primary);
      }

      .bar-header .value {
        font-size: 0.85em;
        font-weight: 600;
        color: var(--text-primary);
      }

      .bar-track {
        height: 6px;
        border-radius: 3px;
        background: var(--divider);
        overflow: hidden;
      }

      .bar-fill {
        height: 100%;
        border-radius: 3px;
        background: var(--green);
        transition: width 0.5s ease;
        min-width: 0;
      }

      .bar-fill.accent {
        background: var(--accent);
      }

      /* ── Sensor grid ── */

      .sensor-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: 8px;
      }

      .sensor-item {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 10px;
        border-radius: 8px;
        background: var(--divider);
      }

      .sensor-item ha-icon {
        --mdc-icon-size: 18px;
        color: var(--text-secondary);
      }

      .sensor-item .name {
        flex: 1;
        font-size: 0.8em;
        color: var(--text-primary);
      }

      .sensor-item .value {
        font-size: 0.85em;
        font-weight: 600;
        color: var(--text-primary);
        white-space: nowrap;
      }

      /* ── Alarms ── */

      .alarm-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: 8px;
      }

      .alarm-item {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 10px;
        border-radius: 8px;
      }

      .alarm-item.normal {
        background: color-mix(in srgb, var(--green) 12%, transparent);
      }

      .alarm-item.active {
        background: color-mix(in srgb, var(--red) 15%, transparent);
        animation: pulse 2s infinite;
      }

      @keyframes pulse {
        0%,
        100% {
          opacity: 1;
        }
        50% {
          opacity: 0.7;
        }
      }

      .alarm-item ha-icon {
        --mdc-icon-size: 18px;
      }

      .alarm-item.normal ha-icon {
        color: var(--green);
      }

      .alarm-item.active ha-icon {
        color: var(--red);
      }

      .alarm-item .name {
        flex: 1;
        font-size: 0.8em;
        color: var(--text-primary);
      }

      .alarm-item .status {
        font-size: 0.7em;
        font-weight: 700;
      }

      .alarm-item.normal .status {
        color: var(--green);
      }

      .alarm-item.active .status {
        color: var(--red);
      }

      /* ── PID ── */

      .pid-card {
        background: var(--divider);
        border-radius: 12px;
        padding: 12px;
      }

      .pid-params {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
        gap: 8px;
      }

      .pid-param {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        padding: 8px 4px;
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.06);
      }

      .pid-param.highlight {
        background: color-mix(in srgb, var(--accent) 15%, transparent);
      }

      .pid-label {
        font-size: 0.65em;
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .pid-value {
        font-size: 1em;
        font-weight: 600;
        color: var(--text-primary);
      }

      .pid-param.highlight .pid-value {
        color: var(--accent);
      }
    `;
  }
}

/* ── Card editor ── */

class RevPiBuildingCardEditor extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      _config: { type: Object },
    };
  }

  setConfig(config) {
    this._config = { ...config };
  }

  _getDevices() {
    if (!this.hass) return [];
    return Object.values(this.hass.devices || {}).filter((d) => {
      const ids = d.identifiers || [];
      return ids.some(
        ([domain, id]) => domain === "ha_revpi" && id.includes("_bld")
      );
    });
  }

  _deviceChanged(ev) {
    const deviceId = ev.target.value;
    this._config = { ...this._config, device_id: deviceId };
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config: this._config } })
    );
  }

  _titleChanged(ev) {
    this._config = { ...this._config, title: ev.target.value };
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config: this._config } })
    );
  }

  render() {
    if (!this.hass || !this._config) return html``;
    const devices = this._getDevices();

    return html`
      <div class="editor">
        <label>Building Device</label>
        <select
          .value=${this._config.device_id || ""}
          @change=${this._deviceChanged}
        >
          <option value="">Select a building device...</option>
          ${devices.map(
            (d) =>
              html`<option
                value=${d.id}
                ?selected=${d.id === this._config.device_id}
              >
                ${d.name} (${d.model || "Device"})
              </option>`
          )}
        </select>
        <label>Title (optional)</label>
        <input
          type="text"
          .value=${this._config.title || ""}
          placeholder="Auto-detect from device"
          @input=${this._titleChanged}
        />
      </div>
    `;
  }

  static get styles() {
    return css`
      .editor {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 16px;
      }
      label {
        font-weight: 500;
        font-size: 0.9em;
      }
      select,
      input {
        padding: 8px;
        border: 1px solid var(--divider-color, #ccc);
        border-radius: 4px;
        font-size: 0.9em;
      }
    `;
  }
}

customElements.define("revpi-building-card", RevPiBuildingCard);
customElements.define("revpi-building-card-editor", RevPiBuildingCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "revpi-building-card",
  name: "RevPi Building Device Card",
  description:
    "Visualize a Revolution Pi building device with climate, fans, dampers, valves, alarms, and PID controller.",
  preview: true,
});
