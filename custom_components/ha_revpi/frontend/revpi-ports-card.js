import { LitElement, html, css } from "https://unpkg.com/lit?module";

class RevPiPortsCard extends LitElement {
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
    return 5;
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

  /* ── Module type detection ── */

  _getModuleType() {
    if (!this.hass || !this.config.device_id) return "generic";
    const device = this.hass.devices?.[this.config.device_id];
    if (!device) return "generic";
    const hw = (device.hw_version || "").toLowerCase();
    if (["mio", "dio", "aio", "ro", "core"].includes(hw)) return hw;
    // Fallback: detect core by entity patterns
    if (this._deviceEntities.some((eid) => eid.includes("cpu_temperature")))
      return "core";
    return "generic";
  }

  /* ── Entity helpers ── */

  _isDigital(state) {
    const s = state?.toUpperCase();
    return s === "ON" || s === "OFF" || s === "TRUE" || s === "FALSE";
  }

  _isOn(state) {
    const s = state?.toLowerCase();
    return s === "on" || s === "true";
  }

  _getDigitalInputs() {
    return this._deviceEntities.filter((eid) => {
      if (!eid.startsWith("sensor.")) return false;
      if (this._isOutputSensor(eid)) return false;
      const entity = this.hass.states[eid];
      return entity && this._isDigital(entity.state);
    });
  }

  _isOutputSensor(eid) {
    // Output monitoring sensors may have _out_sensor in entity_id or
    // "(output)" in friendly name (HA slugifies names differently)
    if (eid.includes("_out_sensor") || eid.includes("_output")) return true;
    const entity = this.hass.states[eid];
    if (entity?.attributes?.friendly_name?.includes("(output)")) return true;
    return false;
  }

  _getAnalogueInputs() {
    return this._deviceEntities.filter((eid) => {
      if (!eid.startsWith("sensor.")) return false;
      if (this._isOutputSensor(eid)) return false;
      const entity = this.hass.states[eid];
      return entity && !this._isDigital(entity.state);
    });
  }

  _getDigitalOutputs() {
    return this._deviceEntities.filter((eid) => eid.startsWith("switch."));
  }

  _getAnalogueOutputs() {
    return this._deviceEntities.filter((eid) => eid.startsWith("number."));
  }

  _getAnalogueOutputSensors() {
    return this._deviceEntities.filter(
      (eid) => eid.startsWith("sensor.") && this._isOutputSensor(eid)
    );
  }

  _getAllSensors() {
    return this._deviceEntities.filter((eid) => eid.startsWith("sensor."));
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

  _extractNumber(entityId) {
    const match = entityId.match(/(\d+)(?:_sensor|_out_sensor)?$/);
    return match ? parseInt(match[1]) : 0;
  }

  _getDeviceName() {
    if (!this.hass || !this.config.device_id) return null;
    const device = this.hass.devices?.[this.config.device_id];
    return device?.name || null;
  }

  async _toggleSwitch(entityId) {
    const entity = this.hass.states[entityId];
    if (!entity) return;
    const service = entity.state === "on" ? "turn_off" : "turn_on";
    await this.hass.callService("switch", service, { entity_id: entityId });
  }

  /* ── Sort helper ── */

  _sortByNum(arr) {
    return [...arr].sort(
      (a, b) => this._extractNumber(a) - this._extractNumber(b)
    );
  }

  /* ── Render dispatch ── */

  render() {
    if (!this.hass || !this.config) return html``;

    const moduleType = this._getModuleType();
    const title =
      this.config.title || this._getDeviceName() || "RevPi Module";

    switch (moduleType) {
      case "core":
        return this._renderCore(title);
      case "mio":
        return this._renderMIO(title);
      case "dio":
        return this._renderDIO(title);
      case "aio":
        return this._renderAIO(title);
      case "ro":
        return this._renderRO(title);
      default:
        return this._renderGeneric(title);
    }
  }

  /* ── Header ── */

  _renderHeader(title, badge, badgeClass) {
    return html`
      <div class="module-header">
        <span class="module-badge ${badgeClass}">${badge}</span>
        <span class="module-title">${title}</span>
      </div>
    `;
  }

  /* ── Core (CPU) render ── */

  _renderCore(title) {
    const sensors = this._getAllSensors();
    return html`
      <ha-card>
        ${this._renderHeader(title, "CPU", "core")}
        <div class="card-content core-content">
          ${sensors.map((eid) => {
            const entity = this.hass.states[eid];
            if (!entity) return html``;
            const name = this._getShortName(eid);
            const unit = entity.attributes?.unit_of_measurement || "";
            return html`
              <div class="core-row">
                <span class="core-label">${name}</span>
                <span class="core-value-box"
                  >${entity.state}${unit ? ` ${unit}` : ""}</span
                >
              </div>
            `;
          })}
        </div>
      </ha-card>
    `;
  }

  /* ── MIO render ── */

  _renderMIO(title) {
    const digitalInputs = this._sortByNum(this._getDigitalInputs());
    const analogueInputs = this._sortByNum(this._getAnalogueInputs());
    const analogueOutputs = this._sortByNum(this._getAnalogueOutputs());
    const analogueOutSensors = this._sortByNum(
      this._getAnalogueOutputSensors()
    );
    const digitalOutputs = this._sortByNum(this._getDigitalOutputs());

    return html`
      <ha-card>
        ${this._renderHeader(title, "MIO", "mio")}
        <div class="card-content">
          ${digitalOutputs.length > 0
            ? this._renderDigitalOutputTopStrip(digitalOutputs)
            : ""}
          ${this._renderAnalogueConnectorSection(
            analogueOutputs,
            analogueOutSensors,
            analogueInputs
          )}
          ${digitalInputs.length > 0
            ? html`
                <div class="section-label">DIGITAL INPUTS</div>
                ${this._renderDigitalInputStrip(digitalInputs)}
              `
            : ""}
        </div>
      </ha-card>
    `;
  }

  /* ── DIO render ── */

  _renderDIO(title) {
    const digitalInputs = this._sortByNum(this._getDigitalInputs());
    const digitalOutputs = this._sortByNum(this._getDigitalOutputs());

    // Determine sub-badge based on what's present
    let badge = "DIO";
    if (digitalInputs.length > 0 && digitalOutputs.length === 0) badge = "DI";
    if (digitalInputs.length === 0 && digitalOutputs.length > 0) badge = "DO";

    return html`
      <ha-card>
        ${this._renderHeader(title, badge, "dio")}
        <div class="card-content">
          ${digitalInputs.length > 0
            ? html`
                <div class="section-label">INPUTS</div>
                ${this._renderDigitalInputStrip(digitalInputs)}
              `
            : ""}
          ${digitalOutputs.length > 0
            ? html`
                <div class="section-label">OUTPUTS</div>
                ${this._renderDigitalOutputStrip(digitalOutputs)}
              `
            : ""}
        </div>
      </ha-card>
    `;
  }

  /* ── AIO render ── */

  _renderAIO(title) {
    const analogueInputs = this._sortByNum(this._getAnalogueInputs());
    const analogueOutputs = this._sortByNum(this._getAnalogueOutputs());
    const analogueOutSensors = this._sortByNum(
      this._getAnalogueOutputSensors()
    );

    return html`
      <ha-card>
        ${this._renderHeader(title, "AIO", "aio")}
        <div class="card-content">
          ${this._renderAnalogueConnectorSection(
            analogueOutputs,
            analogueOutSensors,
            analogueInputs
          )}
        </div>
      </ha-card>
    `;
  }

  /* ── RO (Relay) render ── */

  _renderRO(title) {
    const relays = this._sortByNum(this._getDigitalOutputs());
    return html`
      <ha-card>
        ${this._renderHeader(title, "RO", "relay")}
        <div class="card-content">
          <div class="relay-grid">
            ${relays.map((eid) => {
              const entity = this.hass.states[eid];
              if (!entity) return html``;
              const name = this._getShortName(eid);
              const isOn = entity.state === "on";
              return html`
                <div
                  class="relay-item ${isOn ? "on" : "off"}"
                  @click=${() => this._toggleSwitch(eid)}
                >
                  <div class="relay-indicator ${isOn ? "on" : "off"}"></div>
                  <span class="relay-name">${name}</span>
                  <span class="relay-state"
                    >${isOn ? "CLOSED" : "OPEN"}</span
                  >
                </div>
              `;
            })}
          </div>
        </div>
      </ha-card>
    `;
  }

  /* ── Generic fallback ── */

  _renderGeneric(title) {
    const inputs = [
      ...this._getDigitalInputs(),
      ...this._getAnalogueInputs(),
    ];
    const outputs = [
      ...this._getDigitalOutputs(),
      ...this._getAnalogueOutputs(),
    ];
    return html`
      <ha-card>
        ${this._renderHeader(title, "IO", "generic")}
        <div class="card-content">
          ${inputs.length > 0
            ? html`
                <div class="section-label">INPUTS</div>
                <div class="port-grid">
                  ${inputs.map((eid) => this._renderGenericInput(eid))}
                </div>
              `
            : ""}
          ${outputs.length > 0
            ? html`
                <div class="section-label">OUTPUTS</div>
                <div class="port-grid">
                  ${outputs.map((eid) => this._renderGenericOutput(eid))}
                </div>
              `
            : ""}
          ${inputs.length === 0 && outputs.length === 0
            ? html`<p class="no-ports">
                No ports found for this device.
              </p>`
            : ""}
        </div>
      </ha-card>
    `;
  }

  _renderGenericInput(eid) {
    const entity = this.hass.states[eid];
    if (!entity || this._isOutputSensor(eid)) return html``;
    const name = this._getShortName(eid);
    const digital = this._isDigital(entity.state);
    const on = this._isOn(entity.state);
    return html`
      <div class="port-item ${digital ? (on ? "on" : "off") : ""}">
        <span class="name">${name}</span>
        <span class="value">${digital ? (on ? "●" : "○") : entity.state}</span>
      </div>
    `;
  }

  _renderGenericOutput(eid) {
    const entity = this.hass.states[eid];
    if (!entity) return html``;
    const name = this._getShortName(eid);
    if (eid.startsWith("switch.")) {
      const isOn = entity.state === "on";
      return html`
        <div class="port-item ${isOn ? "on" : "off"}">
          <span class="name">${name}</span>
          <button
            class="toggle-btn ${isOn ? "on" : "off"}"
            @click=${() => this._toggleSwitch(eid)}
          >
            ${isOn ? "ON" : "OFF"}
          </button>
        </div>
      `;
    }
    return html`
      <div class="port-item">
        <span class="name">${name}</span>
        <span class="value">${entity.state}</span>
      </div>
    `;
  }

  /* ══════════════════════════════════════════════
     Shared sub-renderers
     ══════════════════════════════════════════════ */

  /* ── Digital input strip (horizontal row, numbered) ── */

  _renderDigitalInputStrip(inputs) {
    // Number sequentially 1..N (physical module labels), show highest first
    const count = inputs.length;
    const reversed = [...inputs].reverse();
    return html`
      <div class="di-strip">
        <div class="di-strip-row">
          ${reversed.map((_eid, idx) => {
            // reversed[0] is the last input → display number = count - idx
            const displayNum = count - idx;
            return html`<span class="di-num">${displayNum}</span>`;
          })}
        </div>
        <div class="di-strip-row">
          ${reversed.map((eid) => {
            const entity = this.hass.states[eid];
            const on = entity && this._isOn(entity.state);
            return html`
              <span class="di-val ${on ? "on" : "off"}"
                >${entity?.state || "?"}</span
              >
            `;
          })}
        </div>
      </div>
    `;
  }

  /* ── Digital output top strip (toggleable, numbered) ── */

  _renderDigitalOutputTopStrip(outputs) {
    // Number sequentially 1..N, show highest first (4, 3, 2, 1)
    const count = outputs.length;
    const reversed = [...outputs].reverse();
    return html`
      <div class="di-strip">
        <div class="di-strip-row">
          ${reversed.map((_eid, idx) => {
            const displayNum = count - idx;
            return html`<span class="di-num">${displayNum}</span>`;
          })}
        </div>
        <div class="di-strip-row">
          ${reversed.map((eid) => {
            const entity = this.hass.states[eid];
            const isOn = entity?.state === "on";
            return html`
              <span
                class="di-val clickable ${isOn ? "on" : "off"}"
                @click=${() => this._toggleSwitch(eid)}
                >${isOn ? "ON" : "OFF"}</span
              >
            `;
          })}
        </div>
      </div>
    `;
  }

  /* ── Inline analogue output editing ── */

  _startEdit(entityId) {
    const entity = this.hass.states[entityId];
    this._editingEntity = entityId;
    this._editValue = entity?.state || "0";
    this.requestUpdate();
    // Focus the input after render
    this.updateComplete.then(() => {
      const input = this.shadowRoot?.querySelector(".conn-edit-input");
      if (input) {
        input.focus();
        input.select();
      }
    });
  }

  async _commitEdit() {
    if (!this._editingEntity) return;
    const val = parseFloat(this._editValue);
    if (!isNaN(val)) {
      await this.hass.callService("number", "set_value", {
        entity_id: this._editingEntity,
        value: val,
      });
    }
    this._editingEntity = null;
    this._editValue = "";
  }

  _cancelEdit() {
    this._editingEntity = null;
    this._editValue = "";
  }

  _handleEditKeydown(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      this._commitEdit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      this._cancelEdit();
    }
  }

  /* ── Analogue connector section (dual-column with pin visuals) ── */

  _renderAnalogueConnectorSection(outputs, outputSensors, inputs) {
    const outputRows = this._buildConnectorRows(
      outputs,
      outputSensors,
      "OUT"
    );
    const inputRows = this._buildConnectorRows(inputs, [], "IN");
    if (outputRows.length === 0 && inputRows.length === 0) return html``;

    return html`
      <div class="connector-section">
        ${outputRows.map((row) => this._renderConnectorRow(row))}
        ${inputRows.length > 0 && outputRows.length > 0
          ? html`<div class="connector-divider"></div>`
          : ""}
        ${inputRows.map((row) => this._renderConnectorRow(row))}
      </div>
    `;
  }

  _buildConnectorRows(entities, sensors, prefix) {
    if (entities.length === 0) return [];

    const numbered = entities.map((eid) => ({
      eid,
      num: this._extractNumber(eid),
      entity: this.hass.states[eid],
      name: this._getShortName(eid),
    }));

    // Map output sensors by number for read-back values
    const sensorMap = {};
    sensors.forEach((eid) => {
      const num = this._extractNumber(eid);
      sensorMap[num] = this.hass.states[eid];
    });

    // Sort descending by number (highest at top, like physical connector)
    numbered.sort((a, b) => b.num - a.num);

    // Pair: left = even index (higher number), right = odd index (lower number)
    const rows = [];
    for (let i = 0; i < numbered.length; i += 2) {
      const left = numbered[i];
      const right = i + 1 < numbered.length ? numbered[i + 1] : null;
      rows.push({
        left: left
          ? {
              ...left,
              label: left.num ? `${prefix} ${left.num}` : left.name,
              sensor: sensorMap[left.num],
            }
          : null,
        right: right
          ? {
              ...right,
              label: right.num ? `${prefix} ${right.num}` : right.name,
              sensor: sensorMap[right.num],
            }
          : null,
      });
    }
    return rows;
  }

  _renderConnectorRow(row) {
    return html`
      <div class="connector-row signal-row">
        <span class="conn-label left">${row.left?.label || ""}</span>
        ${this._renderConnectorValue(row.left, "left")}
        <span class="conn-pin signal"></span>
        <span class="conn-pin signal"></span>
        ${this._renderConnectorValue(row.right, "right")}
        <span class="conn-label right">${row.right?.label || ""}</span>
      </div>
      <div class="connector-row gnd-row">
        <span class="conn-label left gnd-text">GND</span>
        <span class="conn-gnd-spacer"></span>
        <span class="conn-pin gnd"></span>
        <span class="conn-pin gnd"></span>
        <span class="conn-gnd-spacer"></span>
        <span class="conn-label right gnd-text">GND</span>
      </div>
    `;
  }

  _renderConnectorValue(item, side) {
    if (!item) return html`<span class="conn-value ${side}"></span>`;

    const isEditable = item.eid?.startsWith("number.");
    const isEditing = this._editingEntity === item.eid;
    const val = this._connectorVal(item);

    if (isEditing) {
      return html`
        <input
          class="conn-edit-input ${side}"
          type="number"
          .value=${this._editValue}
          @input=${(e) => (this._editValue = e.target.value)}
          @keydown=${(e) => this._handleEditKeydown(e)}
          @blur=${() => this._commitEdit()}
        />
      `;
    }

    if (isEditable) {
      return html`
        <span
          class="conn-value ${side} editable"
          @click=${() => this._startEdit(item.eid)}
          title="Click to edit"
          >${val}</span
        >
      `;
    }

    return html`<span class="conn-value ${side}">${val}</span>`;
  }

  _connectorVal(item) {
    if (!item.entity) return "—";
    const state = item.entity.state;
    if (state === "unavailable" || state === "unknown") return "—";
    return state;
  }

  /* ── Digital output strip (grid with toggles) ── */

  _renderDigitalOutputStrip(outputs) {
    return html`
      <div class="do-strip">
        ${outputs.map((eid) => {
          const entity = this.hass.states[eid];
          if (!entity) return html``;
          const name = this._getShortName(eid);
          const isOn = entity.state === "on";
          return html`
            <div class="do-item ${isOn ? "on" : "off"}">
              <span class="do-name">${name}</span>
              <button
                class="do-toggle ${isOn ? "on" : "off"}"
                @click=${() => this._toggleSwitch(eid)}
              >
                ${isOn ? "ON" : "OFF"}
              </button>
            </div>
          `;
        })}
      </div>
    `;
  }

  /* ══════════════════════════════════════════════
     Styles
     ══════════════════════════════════════════════ */

  static get styles() {
    return css`
      :host {
        --revpi-orange: #e8650a;
        --revpi-light-orange: rgba(232, 101, 10, 0.1);
        --connector-orange: #d4600e;
        --gnd-grey: #9e9e9e;
      }

      /* ── Header ── */
      .module-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px 16px 8px;
      }
      .module-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: white;
      }
      .module-badge.mio {
        background: var(--revpi-orange);
      }
      .module-badge.dio {
        background: #1976d2;
      }
      .module-badge.aio {
        background: #7b1fa2;
      }
      .module-badge.relay {
        background: #d32f2f;
      }
      .module-badge.core {
        background: #455a64;
      }
      .module-badge.generic {
        background: var(--secondary-text-color);
      }
      .module-title {
        font-size: 16px;
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .card-content {
        padding: 8px 16px 16px;
      }
      .section-label {
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
        color: var(--secondary-text-color);
        margin: 12px 0 6px;
      }

      /* ── Core ── */
      .core-content {
        padding: 4px 16px 16px;
      }
      .core-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 12px;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }
      .core-row:last-child {
        border-bottom: none;
      }
      .core-label {
        font-size: 14px;
        color: var(--primary-text-color);
      }
      .core-value-box {
        font-size: 14px;
        font-weight: 600;
        padding: 4px 12px;
        border: 2px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        background: var(--card-background-color, #fff);
        min-width: 60px;
        text-align: center;
      }

      /* ── Digital Input Strip ── */
      .di-strip {
        background: var(--revpi-light-orange);
        border: 1px solid var(--revpi-orange);
        border-radius: 8px;
        padding: 8px 12px;
        margin-bottom: 12px;
      }
      .di-strip-row {
        display: flex;
        justify-content: space-around;
        align-items: center;
      }
      .di-num {
        font-size: 13px;
        font-weight: 600;
        color: var(--secondary-text-color);
        text-align: center;
        min-width: 48px;
      }
      .di-val {
        font-size: 13px;
        font-weight: 700;
        padding: 3px 10px;
        border: 2px solid var(--divider-color, #ccc);
        border-radius: 4px;
        text-align: center;
        min-width: 36px;
        background: var(--card-background-color, #fff);
        margin: 4px 2px;
      }
      .di-val.on {
        border-color: var(--success-color, #4caf50);
        color: var(--success-color, #4caf50);
      }
      .di-val.off {
        border-color: var(--divider-color, #ccc);
        color: var(--secondary-text-color);
      }
      .di-val.clickable {
        cursor: pointer;
        user-select: none;
        transition: background 0.15s, border-color 0.15s;
      }
      .di-val.clickable:hover {
        background: rgba(232, 101, 10, 0.15);
      }

      /* ── Analogue Connector Section ── */
      .connector-section {
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
        padding: 6px 4px;
        margin-bottom: 12px;
        background: var(--secondary-background-color, #f5f5f5);
      }
      .connector-row {
        display: grid;
        grid-template-columns: 54px 1fr 18px 18px 1fr 54px;
        align-items: center;
        gap: 3px;
        padding: 2px 4px;
      }
      .conn-label {
        font-size: 10px;
        font-weight: 600;
        color: var(--primary-text-color);
      }
      .conn-label.left {
        text-align: right;
        padding-right: 4px;
      }
      .conn-label.right {
        text-align: left;
        padding-left: 4px;
      }
      .conn-label.gnd-text {
        color: var(--gnd-grey);
        font-size: 9px;
      }
      .conn-value {
        font-size: 12px;
        font-weight: 700;
        padding: 2px 4px;
        border: 2px solid var(--divider-color, #ccc);
        border-radius: 3px;
        text-align: center;
        background: var(--card-background-color, #fff);
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .conn-value.left {
        margin-right: 2px;
      }
      .conn-value.right {
        margin-left: 2px;
      }
      .conn-value.editable {
        cursor: pointer;
        border-color: var(--revpi-orange);
        transition: background 0.15s;
      }
      .conn-value.editable:hover {
        background: var(--revpi-light-orange);
      }
      .conn-edit-input {
        font-size: 12px;
        font-weight: 700;
        padding: 2px 4px;
        border: 2px solid var(--revpi-orange);
        border-radius: 3px;
        text-align: center;
        background: var(--card-background-color, #fff);
        min-width: 0;
        width: 100%;
        box-sizing: border-box;
        outline: none;
        color: var(--primary-text-color);
        -moz-appearance: textfield;
      }
      .conn-edit-input::-webkit-outer-spin-button,
      .conn-edit-input::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
      }
      .conn-edit-input.left {
        margin-right: 2px;
      }
      .conn-edit-input.right {
        margin-left: 2px;
      }
      .conn-pin.signal {
        width: 14px;
        height: 20px;
        background: var(--connector-orange);
        border-radius: 2px;
        justify-self: center;
      }
      .conn-pin.gnd {
        width: 12px;
        height: 12px;
        background: var(--gnd-grey);
        border-radius: 50%;
        justify-self: center;
      }
      .conn-gnd-spacer {
        /* Empty space where value boxes would be on signal rows */
      }
      .gnd-row {
        padding: 1px 4px;
      }
      .connector-divider {
        height: 1px;
        background: var(--divider-color, #e0e0e0);
        margin: 6px 8px;
      }

      /* ── Digital Output Strip ── */
      .do-strip {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        gap: 6px;
      }
      .do-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 10px;
        border-radius: 6px;
        border: 1px solid var(--divider-color, #e0e0e0);
        background: var(--card-background-color, #fff);
      }
      .do-item.on {
        border-color: var(--success-color, #4caf50);
        background: rgba(76, 175, 80, 0.08);
      }
      .do-name {
        font-size: 12px;
        font-weight: 500;
      }
      .do-toggle {
        cursor: pointer;
        padding: 3px 8px;
        border-radius: 4px;
        border: none;
        font-size: 11px;
        font-weight: 700;
      }
      .do-toggle.on {
        background: var(--success-color, #4caf50);
        color: white;
      }
      .do-toggle.off {
        background: var(--divider-color, #e0e0e0);
        color: var(--primary-text-color);
      }

      /* ── Relay Grid ── */
      .relay-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
      }
      .relay-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 12px;
        border-radius: 8px;
        border: 2px solid var(--divider-color, #e0e0e0);
        background: var(--card-background-color, #fff);
        cursor: pointer;
        transition: border-color 0.2s, background 0.2s;
      }
      .relay-item.on {
        border-color: var(--success-color, #4caf50);
        background: rgba(76, 175, 80, 0.08);
      }
      .relay-indicator {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        margin-bottom: 6px;
        transition: background 0.2s;
      }
      .relay-indicator.on {
        background: var(--success-color, #4caf50);
      }
      .relay-indicator.off {
        background: var(--divider-color, #e0e0e0);
      }
      .relay-name {
        font-size: 12px;
        font-weight: 600;
      }
      .relay-state {
        font-size: 10px;
        color: var(--secondary-text-color);
        margin-top: 2px;
      }

      /* ── Generic fallback ── */
      .port-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
        gap: 6px;
      }
      .port-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 10px;
        border-radius: 6px;
        border: 1px solid var(--divider-color, #e0e0e0);
        background: var(--card-background-color, #fff);
      }
      .port-item.on {
        border-color: var(--success-color, #4caf50);
        background: rgba(76, 175, 80, 0.08);
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
      .toggle-btn {
        cursor: pointer;
        padding: 3px 8px;
        border-radius: 4px;
        border: none;
        font-size: 11px;
        font-weight: 700;
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
        font-size: 14px;
        padding: 8px 0;
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
    if (!this.hass || !this._config) return html``;

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
          .selector=${{ device: { integration: "ha_revpi" } }}
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
    description:
      "Module-aware card showing RevPi IO ports with connector-style layouts",
    preview: true,
  });
})();
