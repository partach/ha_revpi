import { LitElement, html, css } from "https://unpkg.com/lit?module";

class RevPiPortsCard extends LitElement {
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
    return document.createElement("revpi-ports-card-editor");
  }

  static getStubConfig() {
    return { device_id: "" };
  }

  setConfig(config) {
    this.config = { ...config };
    this.requestUpdate();
  }

  getCardSize() {
    return 3;
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

  _getEntityId(key) {
    if (!this._deviceEntities?.length) return null;
    const exact = this._deviceEntities.find((eid) => eid.endsWith(`_${key}`));
    if (exact) return exact;
    const re = new RegExp(key.split("_").join("_(?:\\w+_)*"));
    return this._deviceEntities.find((eid) => re.test(eid));
  }

  _getState(key) {
    const eid = this._getEntityId(key);
    if (!eid) return null;
    const entity = this.hass.states[eid];
    if (!entity || entity.state === "unknown" || entity.state === "unavailable")
      return null;
    return entity.state;
  }

  _getInputEntities() {
    return this._deviceEntities.filter(
      (eid) =>
        eid.startsWith("sensor.") && !eid.includes("_out_sensor")
    );
  }

  _getOutputEntities() {
    return this._deviceEntities.filter(
      (eid) =>
        eid.startsWith("switch.") ||
        eid.startsWith("number.") ||
        eid.startsWith("select.")
    );
  }

  _getShortName(entityId) {
    const entity = this.hass.states[entityId];
    const name = entity?.attributes?.friendly_name || entityId.split(".")[1];
    return name.replace(/^revpi_/i, "").replace(/_sensor$/, "");
  }

  _isDigitalOn(state) {
    const s = state?.toLowerCase();
    return s === "on" || s === "true";
  }

  _isDigital(state) {
    const s = state?.toUpperCase();
    return s === "ON" || s === "OFF" || s === "TRUE" || s === "FALSE";
  }

  async _toggleSwitch(entityId) {
    const entity = this.hass.states[entityId];
    if (!entity) return;
    const service = entity.state === "on" ? "turn_off" : "turn_on";
    await this.hass.callService("switch", service, {
      entity_id: entityId,
    });
  }

  render() {
    if (!this.hass || !this.config) return html``;

    const inputs = this._getInputEntities();
    const outputs = this._getOutputEntities();
    const title = this.config.title || this._getDeviceName() || "RevPi Ports";

    return html`
      <ha-card header="${title}">
        <div class="card-content">
          ${inputs.length > 0
            ? html`
                <div class="section">
                  <h3 class="section-title">INPUTS</h3>
                  <div class="port-grid">
                    ${inputs.map((eid) => this._renderInput(eid))}
                  </div>
                </div>
              `
            : ""}
          ${outputs.length > 0
            ? html`
                <div class="section">
                  <h3 class="section-title">OUTPUTS</h3>
                  <div class="port-grid">
                    ${outputs.map((eid) => this._renderOutput(eid))}
                  </div>
                </div>
              `
            : ""}
          ${inputs.length === 0 && outputs.length === 0
            ? html`<p class="no-ports">
                No ports found for this device. Check entity configuration.
              </p>`
            : ""}
        </div>
      </ha-card>
    `;
  }

  _getDeviceName() {
    if (!this.hass || !this.config.device_id) return null;
    const device = this.hass.devices?.[this.config.device_id];
    return device?.name || null;
  }

  _renderInput(entityId) {
    const entity = this.hass.states[entityId];
    if (!entity) return html``;

    const name = this._getShortName(entityId);
    const val = entity.state;
    const digital = this._isDigital(val);
    const on = this._isDigitalOn(val);

    return html`
      <div class="port-item ${digital ? (on ? "on" : "off") : ""}">
        <span class="name" title="${name}">${name}</span>
        <span class="value">${digital ? (on ? "●" : "○") : val}</span>
      </div>
    `;
  }

  _renderOutput(entityId) {
    const entity = this.hass.states[entityId];
    if (!entity) return html``;

    const name = this._getShortName(entityId);

    if (entityId.startsWith("switch.")) {
      const isOn = entity.state === "on";
      return html`
        <div class="port-item ${isOn ? "on" : "off"}">
          <span class="name" title="${name}">${name}</span>
          <button
            class="toggle-btn ${isOn ? "on" : "off"}"
            @click=${() => this._toggleSwitch(entityId)}
          >
            ${isOn ? "ON" : "OFF"}
          </button>
        </div>
      `;
    }

    return html`
      <div class="port-item">
        <span class="name" title="${name}">${name}</span>
        <span class="value">${entity.state}</span>
      </div>
    `;
  }

  static get styles() {
    return css`
      .card-content {
        padding: 16px;
      }
      .section {
        margin-bottom: 16px;
      }
      .section-title {
        margin: 0 0 8px;
        font-size: 14px;
        color: var(--secondary-text-color);
      }
      .port-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: 8px;
      }
      .port-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 12px;
        border-radius: 8px;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
      }
      .port-item .name {
        font-size: 12px;
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 80px;
      }
      .port-item .value {
        font-size: 14px;
        font-weight: 600;
      }
      .port-item.on {
        border-color: var(--success-color, #4caf50);
        background: rgba(76, 175, 80, 0.1);
      }
      .port-item.off {
        border-color: var(--divider-color, #e0e0e0);
      }
      .toggle-btn {
        cursor: pointer;
        padding: 4px 8px;
        border-radius: 4px;
        border: none;
        font-size: 12px;
        font-weight: 600;
      }
      .toggle-btn.on {
        background: var(--success-color, #4caf50);
        color: white;
      }
      .toggle-btn.off {
        background: var(--divider-color, #e0e0e0);
        color: var(--primary-text-color);
      }
      .no-ports {
        color: var(--secondary-text-color);
      }
    `;
  }
}

class RevPiPortsCardEditor extends LitElement {
  static get properties() {
    return {
      hass: {},
      _config: {},
    };
  }

  setConfig(config) {
    this._config = { ...config };
  }

  render() {
    if (!this.hass) return html``;

    return html`
      <style>
        .config-row {
          margin-bottom: 12px;
        }
        ha-textfield {
          width: 100%;
        }
      </style>

      <div class="config-row">
        <ha-textfield
          label="Card Title (optional)"
          .value=${this._config.title || ""}
          @input=${(e) => this._valueChanged("title", e.target.value)}
        ></ha-textfield>
      </div>

      <div class="config-row">
        <ha-selector
          .hass=${this.hass}
          .selector=${{ device: { integration: "revpi" } }}
          .value=${this._config.device_id || ""}
          @value-changed=${(e) =>
            this._valueChanged("device_id", e.detail.value)}
          label="Device"
        ></ha-selector>
      </div>
    `;
  }

  _valueChanged(field, value) {
    const newConfig = { ...this._config, [field]: value };
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: newConfig },
        bubbles: true,
        composed: true,
      })
    );
  }
}

customElements.define("revpi-ports-card", RevPiPortsCard);
customElements.define("revpi-ports-card-editor", RevPiPortsCardEditor);

(function () {
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "revpi-ports-card",
    name: "Revolution Pi Ports",
    description: "Shows status and control of RevPi module ports",
    preview: true,
  });
})();
