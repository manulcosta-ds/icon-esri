// ArcGIS Icon Browser - Main Plugin Code

interface IconData {
  id: string;
  context: string;
  context_key: string;
  icon_name: string;
  icon_key: string;
  size: number;
  component_key: string;
  component_id: string;
  component_name: string;
}

interface PluginMessage {
  type: string;
  iconData?: IconData;
  icons?: IconData[];
}

// Show the plugin UI
figma.showUI(__html__, { 
  width: 600, 
  height: 700,
  themeColors: true
});

// Handle messages from the UI
figma.ui.onmessage = async (msg: PluginMessage) => {
  if (msg.type === 'insert-icon') {
    const iconData = msg.iconData;
    if (!iconData || !iconData.component_key) {
      figma.notify('Error: No component key provided', { error: true });
      return;
    }

    try {
      // Import the component from the library using its key
      const component = await figma.importComponentByKeyAsync(iconData.component_key);
      
      // Create an instance of the component
      const instance = component.createInstance();
      
      // Position at viewport center
      const viewportCenter = figma.viewport.center;
      instance.x = viewportCenter.x - instance.width / 2;
      instance.y = viewportCenter.y - instance.height / 2;
      
      // Select the new instance
      figma.currentPage.selection = [instance];
      
      // Scroll to show the instance
      figma.viewport.scrollAndZoomIntoView([instance]);
      
      figma.notify(`Inserted: ${iconData.icon_name} (${iconData.size}px)`);
      
    } catch (error) {
      console.error('Error importing component:', error);
      figma.notify(`Error: Could not import "${iconData.icon_name}". Make sure the library is enabled.`, { error: true });
    }
  }
  
  if (msg.type === 'insert-multiple') {
    const icons = msg.icons;
    if (!icons || icons.length === 0) {
      figma.notify('No icons selected', { error: true });
      return;
    }

    try {
      const instances: SceneNode[] = [];
      const viewportCenter = figma.viewport.center;
      const spacing = 20;
      let currentX = viewportCenter.x;
      let currentY = viewportCenter.y;
      let maxHeightInRow = 0;
      const maxRowWidth = 400;
      let rowStartX = currentX;

      for (const iconData of icons) {
        const component = await figma.importComponentByKeyAsync(iconData.component_key);
        const instance = component.createInstance();
        
        // Check if we need to wrap to next row
        if (currentX - rowStartX + instance.width > maxRowWidth && instances.length > 0) {
          currentX = rowStartX;
          currentY += maxHeightInRow + spacing;
          maxHeightInRow = 0;
        }
        
        instance.x = currentX;
        instance.y = currentY;
        
        currentX += instance.width + spacing;
        maxHeightInRow = Math.max(maxHeightInRow, instance.height);
        
        instances.push(instance);
      }

      figma.currentPage.selection = instances;
      figma.viewport.scrollAndZoomIntoView(instances);
      
      figma.notify(`Inserted ${icons.length} icons`);
      
    } catch (error) {
      console.error('Error importing components:', error);
      figma.notify('Error importing some icons. Make sure the library is enabled.', { error: true });
    }
  }

  if (msg.type === 'get-cached-data') {
    figma.clientStorage.getAsync('icon-data').then(cached => {
      figma.ui.postMessage({ type: 'cached-data', payload: cached || null });
    });
  }

  if (msg.type === 'cache-data') {
    figma.clientStorage.setAsync('icon-data', msg.payload);
  }

  if (msg.type === 'close') {
    figma.closePlugin();
  }
};
