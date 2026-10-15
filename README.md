# Projector Add-on for Blender
Simple projector creation and modification for [Blender](https://www.blender.org/) 4.2+ LTS.

![Projector Add-on for Blender title image](/.github/gifs/title.jpg)

## Features

### 1. Physically-Accurate 3D Projector & Rigging System
* **Procedural 3D Model Generation**: High-detail physical chassis with cooling louvers, top control panel with buttons and status LEDs (Power, Temp, Lamp), knurled zoom and focus controls, and rear I/O plate (HDMI, USB, Audio, RS-232, IEC AC power inlet, Kensington lock slot).
* **Optical Origin Exit Pupil Alignment**: The projection frustum and spot beam originate exactly at the physical exit pupil of the front lens element at local `(0, 0, 0)`. The lens barrel extends backward into the chassis, ensuring zero internal self-shadowing and 100% optical alignment with Blender cameras and Cycles projection rays.
* **Underside Metric Mounting Points**: 4 M4/M6 threaded brass inserts positioned according to standard manufacturer pitch circle diameters (PCD).
* **Modular Rigging System**:
  * **Tabletop (`NONE`)**: 4 adjustable knurled rubber leveling feet with threaded height-adjustment studs.
  * **Ceiling Mount (`CEILING`)**: Slotted articulated steel spider arms, central gimbal hub with pitch/roll tilt controls, customizable 1.5" NPT extension drop column (`mount_pole_length`), and structural ceiling flange plate with anchor bolt slots. Supports inverted mounting (upside-down) matching standard AV installation.
  * **Theatrical Truss Clamp (`TRUSS`)**: Heavy-duty 50mm (2") Half-Coupler (cheeseborough) clamp with hinge pin, ergonomic T-bar wing handle, and stainless steel aircraft safety cable with screw-lock carabiner.
* **Parametric Auto-Sizing**: Chassis dimensions (Width, Height, Depth, Lens Offset) automatically adjust when selecting a model from the ProjectorCentral database.

### 2. ProjectorCentral Integration & Model Database
* **Built-in Offline Database**: Pre-populated specifications for popular production models from leading brands (BenQ, Epson, Optoma, Panasonic, Sony, Barco, Christie, ViewSonic).
* **On-the-Fly Scraper**: Download specifications directly from [ProjectorCentral.com](https://www.projectorcentral.com) by entering any model name or URL.
* **One-Click Configuration**: Automatically applies Lumens, Throw Ratio, Focus Distance range, Aspect Ratio, Resolution, Lens Shift limits, and physical dimensions.

### 3. Optimal Depth Luminosity & Topological Heatmap
* **Saturated Zero-Gradient Heatmap**: 3 distinctive, high-contrast distance zones with zero gradient stepped transitions:
  * **Yellow**: $< d_{\text{min}}$ (Too close / over-illuminated)
  * **Green**: $d_{\text{opt}}$ (Optimal focus & screen luminance)
  * **Red**: $> d_{\text{max}}$ (Under-illuminated / beyond focused throw)
* **Elevation Contour Isolines**: High-visibility metric elevation contour lines across the projected surface.
* **FOV Frustum Masking**: Clamps projection strictly to the projector's rectangular aspect ratio frame, preventing spotlight hemisphere light bleed.
* **Distance Dimming Compensation**: Cancels physical $1/d^2$ attenuation in Cycles to keep surfaces at maximum distance brightly visible for surveying and mapping.
* **Photometric Lux Readout**: Real-time calculated illuminance in Lux and throw area dimensions at optimal focus distance.

---

## Projectors Add-on in Action

#### Throw Ratio
Control the size of your projection by adjusting the throw ratio to match real-world projector specifications.
![Throw Ratio](/.github/gifs/throw_ratio.gif)

#### Lens Shift
Fine-tune the vertical and horizontal position of your projection without moving the projector itself.
![Lens Shift](/.github/gifs/lens_shift.gif)

#### Image Textures & Resolution
Load your own images or videos and set custom resolutions to match your projection content.
![Image Texture & Resolutions](/.github/gifs/image_textures_resolution.gif)

#### Random Color
Quickly assign random colors to distinguish multiple projectors in your scene.
![Random Color](/.github/gifs/random_color.gif)

---

## Compatibility
* Works with Blender 4.2+ LTS (Cycles Render Engine recommended for physically-based depth ray tracing).

## Installation
1. Download the repository as a ZIP file.
2. In Blender, navigate to **Edit > Preferences > Add-ons**.
3. Click the drop-down menu in the top right, select **Install from Disk...**, and select the `.zip` file.
4. Enable the **Projector** extension.
5. In the 3D Viewport, press **N** to open the sidebar and navigate to the **Projector** tab.

## License
GPLv3 License - see [LICENSE](LICENSE) for details.
