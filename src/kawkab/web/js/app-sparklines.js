window.KawkabSparklines = {
  line(container, data, options) {
    options = options || {};
    var width = options.width || 80;
    var height = options.height || 24;
    var color = options.color || '#2563eb';
    var strokeWidth = options.strokeWidth || 1.5;
    var fill = options.fill !== undefined ? options.fill : true;
    if (!data || data.length < 2) { return; }
    var min = Math.min.apply(null, data);
    var max = Math.max.apply(null, data);
    var range = max - min || 1;
    var stepX = width / (data.length - 1);
    var points = data.map(function (v, i) {
      var x = i * stepX;
      var y = height - ((v - min) / range) * (height - 2) - 1;
      return x + ',' + y;
    }).join(' ');
    var svg = '<svg width="' + width + '" height="' + height + '" viewBox="0 0 ' + width + ' ' + height + '" xmlns="http://www.w3.org/2000/svg">';
    if (fill) {
      var fillPoints = '0,' + height + ' ' + points + ' ' + width + ',' + height;
      svg += '<polygon points="' + fillPoints + '" fill="' + color + '" fill-opacity="0.15" />';
    }
    svg += '<polyline points="' + points + '" fill="none" stroke="' + color + '" stroke-width="' + strokeWidth + '" stroke-linecap="round" stroke-linejoin="round" />';
    svg += '</svg>';
    container.innerHTML = svg;
  },

  bar(container, data, options) {
    options = options || {};
    var width = options.width || 80;
    var height = options.height || 24;
    var color = options.color || '#2563eb';
    if (!data || data.length === 0) { return; }
    var max = Math.max.apply(null, data) || 1;
    var barW = Math.max(2, (width - (data.length - 1) * 1) / data.length);
    var rects = data.map(function (v, i) {
      var barH = (v / max) * (height - 2);
      var x = i * (barW + 1);
      var y = height - barH - 1;
      return '<rect x="' + x + '" y="' + y + '" width="' + barW + '" height="' + barH + '" fill="' + color + '" rx="1" />';
    }).join(' ');
    var svg = '<svg width="' + width + '" height="' + height + '" viewBox="0 0 ' + width + ' ' + height + '" xmlns="http://www.w3.org/2000/svg">' + rects + '</svg>';
    container.innerHTML = svg;
  },

  comparisonBar(container, valueA, valueB, options) {
    options = options || {};
    var width = options.width || 100;
    var height = options.height || 14;
    var colorA = options.colorA || '#2563eb';
    var colorB = options.colorB || '#dc2626';
    var total = Math.abs(valueA) + Math.abs(valueB) || 1;
    var pctA = Math.abs(valueA) / total * 100;
    var svg = '<svg width="' + width + '" height="' + height + '" viewBox="0 0 ' + width + ' ' + height + '" xmlns="http://www.w3.org/2000/svg">' +
      '<rect x="0" y="0" width="' + pctA + '" height="' + height + '" fill="' + colorA + '" rx="2" />' +
      '<rect x="' + pctA + '" y="0" width="' + (width - pctA) + '" height="' + height + '" fill="' + colorB + '" rx="2" />' +
      '</svg>';
    container.innerHTML = svg;
  }
};
