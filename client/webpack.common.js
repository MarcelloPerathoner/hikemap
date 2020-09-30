const glob = require ('glob');
const path = require ('path');

const HtmlWebpackPlugin = require ('html-webpack-plugin');
const VueLoaderPlugin   = require ('vue-loader/lib/plugin'); // loads vue single-file components

module.exports = {
    context : path.resolve (__dirname),
    entry : {
        'client' : './src/js/main.js',
    },
    output : {
        filename : '[name].[contenthash].js',
        path     : path.resolve (__dirname, 'dist'),
    },
    module : {
        rules : [
            {
                test : /\.js$/,
                exclude : /node_modules/,
                use : [
                    'babel-loader',
                ],
            },
            {
                test: /\.vue$/,
                exclude: /node_modules/,
                use: [
                    'vue-loader',
                ],
            },
            {
                test : /\.(png|jpg|jpeg|gif)$/,
                use  : [
                    {
                        loader  : 'file-loader',
                        options : {
                            name       : '[name].[contenthash].[ext]',
                            outputPath : 'images',
                        },
                    },
                ],
            },
            {
                test : /\.(ttf|woff|woff2)$/,
                use  : [
                    {
                        loader  : 'file-loader',
                        options : {
                            name       : '[name].[contenthash].[ext]',
                            outputPath : 'webfonts',
                        },
                    },
                ],
            },
        ],
    },
    plugins: [
        new VueLoaderPlugin (),
    ],
    optimization : {
        runtimeChunk : {
            name : 'runtime',
        },
        moduleIds : 'deterministic',
    },
    plugins : [
        new HtmlWebpackPlugin ({
            template : './src/index.html',
            inject   : false,
            chunks   : [ 'client', 'vendor', 'runtime' ],
        }),
        new VueLoaderPlugin (),
    ],
    resolve : {
        modules : [
            path.join (__dirname, '../node_modules'),
        ],
        alias: {
            'frappe-charts$' : 'frappe-charts/dist/frappe-charts.esm.js',
        },
    },
};
