const path = require ('path');
const { merge } = require ('webpack-merge');
const chokidar = require ('chokidar');
const common = require ('./webpack.common.js');

const host    = 'hikemap.fritz.box';
const devHost = 'localhost';
const devPort = 8080;

module.exports = merge (common, {
    mode    : 'development',
    devtool : 'eval-source-map',
    output  : {
        publicPath  : `http://${devHost}:${devPort}/dist/`,
    },
    module : {
        rules : [
            {
                test : /\.s?css$/,
                use  : [
                    'style-loader',
                    {
                        loader  : 'css-loader',
                        options : {
                            importLoaders : 2,
                        },
                    },
                    'postcss-loader',
                    'sass-loader',
                ],
            },
        ],
    },
    watchOptions : {
        ignored : path.join (__dirname, '../node_modules/**'),
    },
    devServer : {
        host        : devHost,
        port        : devPort,
        publicPath  : '/dist/',
        contentBase : path.join (__dirname, 'dist'),
        contentBasePublicPath : '/dist/',

        // Enable hot module reloading (HMR).
        hot        : true,
        liveReload : false,

        // write images because we still load them the traditional way
        // writeToDisk : true,

        // Needed because we access port devPort from port 80.
        allowedHosts : [host],
        headers      : { 'Access-Control-Allow-Origin' : `http://${host}` },

        historyApiFallback: {
            rewrites: [
                { from: /^\//, to: '/dist/index.html' },
            ],
        },

        // Watch for changes to PHP files and reload the page when one changes.
        // See: https://mikeselander.com/hot-reloading-using-webpack-with-php-file-changes/
        before (app, server) {
            chokidar
                .watch (['themes/**/*.php', 'plugins/*/*.php'], {
                    alwaysStat     : true,
                    atomic         : false,
                    followSymlinks : false,
                    ignoreInitial  : true,
                    persistent     : true,
                    usePolling     : true,
                })
                .on ('all', () => {
                    server.sockWrite (server.sockets, 'content-changed');
                });
        },
    },
});
