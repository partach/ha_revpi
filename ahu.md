<p>&nbsp;</p>
<figure class="image image_resized" style="width:50.63%;"><img src="https://github.com/partach/ha_revpi/blob/main/pictures/lbk circuit.png"></figure>
<h3>Overall Layout</h3>
<p>The diagram shows a <strong>dual-flow AHU</strong> with:</p>
<ul>
  <li><strong>Top yellow line</strong> → Exhaust air (fresh/conditioned air going out of building)</li>
  <li><strong>Bottom pink/green line</strong> → into building/conditioned air (air going into the building)</li>
</ul>
<p>It has two main fans (16, 9) &nbsp;and a <strong>heat recovery wheel</strong> (3) in the middle for energy efficiency.</p>
<h3>Step-by-step explanation (from left to right)</h3>
<p><strong>Left side – Outside Air Intake (Buitenlucht):</strong></p>
<ul>
  <li>Fresh outside air enters from the left (green arrow).</li>
  <li>It first passes through emergency fire valve (after Temperature sensor 1)</li>
  <li>There is a <strong>dP sensor</strong> (2) to monitor how dirty the filter is.</li>
  <li>A Filter (yellow triangle) &nbsp;to remove dust, pollen, etc.</li>
</ul>
<p><strong>Heat Recovery Wheel (Warmtewiel):</strong></p>
<ul>
  <li>This is the large blue/red rotating wheel in the center (3).</li>
  <li>It transfers heat (and sometimes moisture) from the exhaust air to the incoming fresh air (or vice versa in summer).</li>
  <li>This saves a lot of energy because you don’t have to heat or cool the incoming air from scratch.</li>
  <li>The wheel is driven by a small motor? (no controls?)</li>
</ul>
<p><strong>Heating Section (right after mixing):</strong></p>
<ul>
  <li>A <strong>red heating coil</strong> (verwarmer) heats the air when needed (using hot water).</li>
  <li>There is a temperature sensor before it (4) and after it (5).</li>
  <li>There is a pump (6) to switch on/off</li>
  <li>There is a valve (7)</li>
</ul>
<p><strong>Fan Section:</strong></p>
<ul>
  <li>A large <strong>supply fan</strong> (8) pushes the conditioned air into the building.</li>
</ul>
<p><strong>cooling Section :</strong></p>
<ul>
  <li>After the fan(8), the Air get's cooled before going into the building</li>
</ul>
<p>&nbsp;</p>
<p><strong>After cooling– Supply to the building:</strong></p>
<ul>
  <li>The air goes through another section with temperature (T) and pressure (P) sensors.</li>
  <li>Temperature sensor after it to measure air going into the building (10)</li>
  <li>Pressure sensor to measure building pressure (11)</li>
  <li>It is then distributed to the rooms.</li>
</ul>
<p>&nbsp;</p>
<p><strong>Top right part – Exhaust / Return air:</strong></p>
<ul>
  <li>A pressure sensor (13) measuring the pressure of the air vent</li>
  <li>A temperature sensor measuring the outgoing air temperature</li>
  <li>Air from the building returns (yellow line).</li>
  <li>Passes through a filter with dP sensor (15).</li>
  <li>It passes through the <strong>heat recovery wheel</strong> (3) to give its energy to the incoming air.</li>
  <li>Finally, an <strong>exhaust fan</strong> (16) blows the used air outside.</li>
</ul>
<p>&nbsp;</p>
<h3>Legend / Symbols at the bottom</h3>
<ul>
  <li>Green square is reset button (18)</li>
  <li>Red: Fire control (19)</li>
  <li>Timer (20)</li>
  <li>Delta T to prevent oscillation (21)</li>
</ul>
<p>&nbsp;</p>
<h3>Summary – What does this AHU do?</h3>
<p>It takes <strong>fresh outside air</strong>, mixes it with <strong>return air</strong>, recovers energy with a <strong>heat wheel</strong>, filters it, heats or cools it as needed, and supplies comfortable air into the building while exhausting stale air.</p>
<p>&nbsp;</p>
<h3>1. <strong>T = Temperature Sensor</strong> (Temperatuursensor)</h3>
<p><strong>What it measures</strong>: The actual temperature of the air at that specific point in the airflow.</p>
<p><strong>How many are there?</strong> You can see several <strong>T</strong> sensors in the diagram.</p>
<p><strong>Why they are important</strong>:</p>
<ul>
  <li>After the heating coil → to check if the air is heated to the desired temperature.</li>
  <li>Before and after the heat recovery wheel → to measure how efficiently the wheel is recovering heat.</li>
  <li>In the supply duct (going to the rooms) → to ensure the air being supplied to the building has the correct comfort temperature.</li>
  <li>In the return/exhaust air → to see how warm the air coming from the rooms is.</li>
</ul>
<p>The AHU controller uses these T sensors to decide whether to turn on the heating coil, cooling coil, or adjust the heat wheel speed.</p>
<p>&nbsp;</p>
<h3>2. <strong>P = Pressure Sensor</strong> (Druksensor)</h3>
<ul>
  <li><strong>What it measures</strong>: The static air pressure at that location.</li>
  <li><strong>Where you see them</strong>: Mainly on the right side in the supply duct (after the fan) and sometimes in the return air.</li>
  <li><strong>Why they are important</strong>:<ul>
      <li>To monitor if the fan is delivering the correct air pressure to the building’s duct system.</li>
      <li>To detect problems like blocked ducts, closed dampers, or dirty filters.</li>
      <li>Helps maintain the right <strong>air balance</strong> between supply and exhaust.</li>
    </ul>
  </li>
</ul>
<p>&nbsp;</p>
<h3>3. <strong>dP = Differential Pressure Sensor</strong> (Diferentsiaal Druksensor)</h3>
<p>This is the <strong>most important sensor</strong> for maintenance and safety.</p>
<ul>
  <li><strong>What it measures</strong>: The <strong>difference</strong> in pressure before and after a component.</li>
  <li><strong>Where you see them</strong>:<ul>
      <li>Before and after the <strong>filters</strong> (yellow boxes on the in and out air flow).</li>
    </ul>
  </li>
</ul>
<p><strong>Main purposes of dP sensors:</strong></p>
<ul>
  <li><strong>Filter monitoring</strong>: When the filter gets dirty, the pressure difference increases. When dP reaches a certain value, the system gives a "Filter dirty – replace" alarm.</li>
  <li><strong>Fan performance</strong>: Checks if the fan is working properly.</li>
  <li><strong>Heat wheel condition</strong>: Detects if the wheel is getting blocked.</li>
</ul>
<h3>Summary Table</h3>
<figure class="table">
  <table>
    <thead>
      <tr>
        <th>Sensor</th>
        <th>Full Name</th>
        <th>What it measures</th>
        <th>Main Purpose</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>T</strong></td>
        <td>Temperature Sensor</td>
        <td>Air temperature (°C)</td>
        <td>Control heating / cooling / comfort</td>
      </tr>
      <tr>
        <td><strong>P</strong></td>
        <td>Pressure Sensor</td>
        <td>Air pressure (Pa)</td>
        <td>Monitor duct pressure and system balance</td>
      </tr>
      <tr>
        <td><strong>dP</strong></td>
        <td>Differential Pressure Sensor</td>
        <td>Pressure difference (Pa) before/after a part</td>
        <td>Filter monitoring + alarm for maintenance</td>
      </tr>
    </tbody>
  </table>
</figure>
<p>&nbsp;</p>
