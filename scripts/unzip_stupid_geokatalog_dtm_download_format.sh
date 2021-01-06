counter=0
for z in FME_1*.zip; do
    for f in $(unzip -Z1 $z); do
        if [[ $f =~ tif$ ]]; then
            o="./dtm/DTM-2p5m_$(printf "%03d" $counter).tif"
            echo "writing $o ..."
            unzip -p "$z" "$f" > "$o"
            counter=$((counter+1))
        fi
    done
done
